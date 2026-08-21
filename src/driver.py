from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from src.config import Settings
from src.errors import UpstreamProtocolError
from src.mcp_gateway import MCPGateway
from src.model_client import LunitModelClient
from src.prompts import GENERATION_SYSTEM_PROMPT
from src.retrieval import RetrievalRunner
from src.safety import assess_risk
from src.schemas import InputMessage, RetrievalEnvelope
from src.validation import build_repair_instruction, validate_answer
from src.tooling import (
    RETRIEVE_TOOL,
    assistant_message_for_history,
    parse_tool_arguments,
    tool_call_name,
    tool_error_content,
    tool_result_message,
    validated_tool_calls,
)


logger = logging.getLogger(__name__)


class Driver:
    def __init__(
        self,
        settings: Settings,
        model_client: Any | None = None,
        gateway_factory: Callable[[Settings], Any] = MCPGateway,
    ) -> None:
        self.settings = settings
        self.model_client = model_client or LunitModelClient(settings)
        self.gateway_factory = gateway_factory

    async def generate(self, history: list[InputMessage]) -> str:
        loop = asyncio.get_running_loop()
        started = loop.time()
        deadline_safety = min(
            1.0,
            max(0.01, self.settings.request_timeout_seconds * 0.01),
        )
        request_deadline = (
            started
            + self.settings.request_timeout_seconds
            - deadline_safety
        )
        initial_retry_deadline = (
            request_deadline
            - self.settings.final_generation_reserve_seconds
        )
        assessment = assess_risk(history)
        conversation = [message.model_dump() for message in history]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": "Answer the latest user message.",
                        "conversation": conversation,
                        "risk_flags": assessment.model_dump(mode="json"),
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ]
        retrieval_count = 0
        final_content: str | None = None
        last_envelope: RetrievalEnvelope | None = None

        for generation_round in range(self.settings.max_generation_rounds):
            final_phase = retrieval_count > 0
            if final_phase:
                final_budget = request_deadline - loop.time()
                if final_budget <= 0:
                    logger.warning(
                        "generation_timed_out phase=final reason=no_budget"
                    )
                    raise TimeoutError
                try:
                    async with asyncio.timeout(final_budget):
                        assistant = await self.model_client.chat(
                            messages,
                            phase="final",
                            max_retries=1,
                            retry_deadline=request_deadline,
                        )
                except TimeoutError:
                    logger.warning(
                        "generation_timed_out phase=final budget_seconds=%s",
                        round(final_budget, 3),
                    )
                    raise
            else:
                assistant = await self.model_client.chat(
                    messages,
                    tools=(
                        [RETRIEVE_TOOL]
                        if self.settings.retrieval_enabled
                        else None
                    ),
                    phase="initial",
                    retry_deadline=initial_retry_deadline,
                )
            calls = validated_tool_calls(assistant)
            if calls and not self.settings.retrieval_enabled:
                raise UpstreamProtocolError(
                    "Lunit FM attempted a tool call while retrieval is disabled"
                )
            if final_phase and calls:
                raise UpstreamProtocolError(
                    "Lunit FM attempted a tool call during final generation"
                )
            if not calls:
                content = assistant.get("content")
                if isinstance(content, str) and content.strip():
                    logger.info(
                        "generation_complete route=%s generation_rounds=%s "
                        "retrievals=%s",
                        "direct" if retrieval_count == 0 else "rag",
                        generation_round + 1,
                        retrieval_count,
                    )
                    final_content = content.strip()
                    break
                raise UpstreamProtocolError(
                    "Lunit FM returned neither text nor tool calls"
                )

            messages.append(assistant_message_for_history(assistant))
            for call in calls:
                name = tool_call_name(call)
                if name != "retrieve_relevant_content":
                    self._append_tool_result(
                        messages,
                        call,
                        name or "unknown_tool",
                        tool_error_content(
                            "Generation may only call retrieve_relevant_content."
                        ),
                    )
                    continue

                try:
                    arguments = parse_tool_arguments(call)
                    query = arguments.get("query")
                    if not isinstance(query, str) or not query.strip():
                        raise ValueError("query must be a non-empty string")
                except (ValueError, json.JSONDecodeError) as exc:
                    self._append_tool_result(
                        messages,
                        call,
                        name,
                        tool_error_content(f"Invalid retrieval query: {exc}"),
                    )
                    continue

                if retrieval_count >= self.settings.max_retrievals_per_answer:
                    self._append_tool_result(
                        messages,
                        call,
                        name,
                        tool_error_content(
                            "Retrieval budget for this answer is exhausted."
                        ),
                    )
                    continue

                retrieval_count += 1
                runner = RetrievalRunner(
                    self.settings,
                    self.model_client,
                    gateway_factory=self.gateway_factory,
                )
                retrieval_started = loop.time()
                elapsed = loop.time() - started
                available = (
                    self.settings.request_timeout_seconds
                    - elapsed
                    - self.settings.final_generation_reserve_seconds
                    - deadline_safety
                )
                retrieval_budget = min(
                    self.settings.retrieval_timeout_seconds,
                    available,
                )
                if retrieval_budget <= 0:
                    logger.warning(
                        "retrieval_skipped reason=final_generation_reserve"
                    )
                    envelope = RetrievalEnvelope(
                        status="no_evidence",
                        note=(
                            "Retrieval was skipped to preserve time for the final "
                            "Generation response."
                        ),
                    )
                else:
                    try:
                        async with asyncio.timeout(retrieval_budget):
                            envelope = await runner.run(
                                query,
                                deadline=loop.time() + retrieval_budget,
                            )
                    except TimeoutError:
                        logger.warning(
                            "retrieval_timed_out budget_seconds=%s",
                            round(retrieval_budget, 3),
                        )
                        envelope = RetrievalEnvelope(
                            status="no_evidence",
                            note=(
                                "Retrieval exceeded its time budget; answer using "
                                "available knowledge and state important uncertainty."
                            ),
                        )
                logger.info(
                    "retrieval_complete status=%s latency_ms=%s budget_seconds=%s",
                    envelope.status,
                    round((loop.time() - retrieval_started) * 1000),
                    round(max(0.0, retrieval_budget), 3),
                )
                last_envelope = envelope
                self._append_tool_result(
                    messages,
                    call,
                    name,
                    envelope.model_dump_json(exclude_none=True),
                )
        else:
            raise UpstreamProtocolError(
                "Lunit FM did not produce a final answer within the round budget"
            )

        if final_content is None:
            raise UpstreamProtocolError("Lunit FM returned no final answer")

        if last_envelope is not None:
            result = validate_answer(
                final_content, last_envelope.evidence, last_envelope.status
            )
            if result.has_gap:
                remaining = request_deadline - loop.time()
                if remaining >= self.settings.citation_repair_min_seconds:
                    messages.append(
                        assistant_message_for_history(
                            {"role": "assistant", "content": final_content}
                        )
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": json.dumps(
                                build_repair_instruction(result),
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        }
                    )
                    try:
                        async with asyncio.timeout(remaining):
                            repaired = await self.model_client.chat(
                                messages,
                                tools=[RETRIEVE_TOOL],
                                tool_choice="none",
                                phase="final",
                                max_retries=0,
                                retry_deadline=request_deadline,
                            )
                        repaired_content = repaired.get("content")
                        if isinstance(repaired_content, str) and repaired_content.strip():
                            final_content = repaired_content.strip()
                        else:
                            logger.warning("citation_repair_empty_response")
                    except TimeoutError:
                        logger.warning(
                            "citation_repair_timed_out budget_seconds=%s",
                            round(remaining, 3),
                        )
                else:
                    logger.info(
                        "citation_repair_skipped reason=insufficient_time_budget"
                    )

        return final_content

    @staticmethod
    def _append_tool_result(
        messages: list[dict[str, Any]],
        call: dict[str, Any],
        name: str,
        content: str,
    ) -> None:
        try:
            messages.append(tool_result_message(call, name, content))
        except ValueError as exc:
            raise UpstreamProtocolError("Lunit FM tool call has no id") from exc

    async def aclose(self) -> None:
        close = getattr(self.model_client, "aclose", None)
        if close is not None:
            await close()
