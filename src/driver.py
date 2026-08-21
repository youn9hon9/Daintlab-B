from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from src.config import Settings
from src.deterministic_router import build_query, classify_route
from src.errors import UpstreamProtocolError
from src.evidence_compiler import compile_evidence
from src.guidance import assess_response_guidance
from src.mcp_gateway import MCPGateway
from src.model_client import LunitModelClient
from src.prompts import GENERATION_SYSTEM_PROMPT
from src.readability import assess_readability
from src.safety import assess_risk
from src.schemas import EvidencePacket, InputMessage
from src.tooling import validated_tool_calls
from src.validation import (
    assess_citation_grounding,
    remove_unknown_citations,
    validate_answer,
)


logger = logging.getLogger(__name__)


class Driver:
    """F010: deterministic router + evidence compiler + exactly one L2 call.

    The old Generation-L2 -> Retrieval-L2 -> final-L2 loop (src/retrieval.py,
    RETRIEVE_TOOL/FINALIZE_TOOL) is gone. Routing, query construction, tool
    selection, and evidence compaction are all decided by harness code
    before the single L2 call; L2 only writes the final natural-language
    answer, offered no tools at all.
    """

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
            started + self.settings.request_timeout_seconds - deadline_safety
        )

        assessment = assess_risk(history)
        guidance = assess_response_guidance(history, assessment)
        route = classify_route(history)

        evidence_packet = await self._compile_evidence_if_needed(
            route, history, request_deadline, loop
        )

        conversation = [message.model_dump() for message in history]
        payload: dict[str, Any] = {
            "conversation": conversation,
            "risk_flags": assessment.model_dump(mode="json"),
            "response_guidance": guidance.model_dump(mode="json"),
        }
        if evidence_packet is not None:
            payload["evidence"] = evidence_packet.model_dump(mode="json")

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    payload, ensure_ascii=False, separators=(",", ":")
                ),
            },
        ]

        final_content = await self._generate_once(
            messages, request_deadline, loop
        )
        logger.info(
            "generation_complete route=%s l2_calls=1 evidence_items=%s",
            route,
            len(evidence_packet.items) if evidence_packet else 0,
        )

        if evidence_packet is not None and evidence_packet.items:
            final_content = self._validate_citations(
                final_content, evidence_packet
            )

        readability = assess_readability(final_content)
        logger.info(
            "readability_checked sentences=%s long_sentences=%s "
            "max_sentence_chars=%s",
            readability.sentence_count,
            readability.long_sentence_count,
            readability.max_sentence_chars,
        )

        return final_content

    async def _compile_evidence_if_needed(
        self,
        route: str,
        history: list[InputMessage],
        request_deadline: float,
        loop: asyncio.AbstractEventLoop,
    ) -> EvidencePacket | None:
        if route == "direct":
            return None

        available = (
            request_deadline
            - loop.time()
            - self.settings.final_generation_reserve_seconds
        )
        evidence_budget = min(
            self.settings.evidence_compiler_timeout_seconds, available
        )
        if evidence_budget <= 0:
            logger.warning(
                "evidence_compiler_skipped reason=final_generation_reserve "
                "route=%s",
                route,
            )
            return None

        query = build_query(history)
        evidence_started = loop.time()
        evidence_packet: EvidencePacket | None = None
        try:
            async with asyncio.timeout(evidence_budget):
                evidence_packet = await compile_evidence(
                    route,
                    query,
                    self.settings,
                    gateway_factory=self.gateway_factory,
                )
        except TimeoutError:
            logger.warning(
                "evidence_compiler_timed_out route=%s budget_seconds=%s",
                route,
                round(evidence_budget, 3),
            )
        logger.info(
            "evidence_compiler_complete route=%s status=%s items=%s "
            "latency_ms=%s",
            route,
            evidence_packet.status if evidence_packet else "no_evidence",
            len(evidence_packet.items) if evidence_packet else 0,
            round((loop.time() - evidence_started) * 1000),
        )
        return evidence_packet

    async def _generate_once(
        self,
        messages: list[dict[str, Any]],
        request_deadline: float,
        loop: asyncio.AbstractEventLoop,
    ) -> str:
        remaining = request_deadline - loop.time()
        if remaining <= 0:
            logger.warning("generation_timed_out phase=initial reason=no_budget")
            raise TimeoutError
        try:
            async with asyncio.timeout(remaining):
                # F010: no tools offered, and no retry -- a ~50s upstream
                # timeout repeated on retry could exceed the whole request
                # budget for a single, already-precious L2 call.
                assistant = await self.model_client.chat(
                    messages,
                    phase="initial",
                    max_retries=0,
                )
        except TimeoutError:
            logger.warning(
                "generation_timed_out phase=initial budget_seconds=%s",
                round(remaining, 3),
            )
            raise

        calls = validated_tool_calls(assistant)
        if calls:
            raise UpstreamProtocolError(
                "Lunit FM attempted a tool call but no tools were offered"
            )
        content = assistant.get("content")
        if not isinstance(content, str) or not content.strip():
            raise UpstreamProtocolError("Lunit FM returned no content")
        return content.strip()

    @staticmethod
    def _validate_citations(
        final_content: str, evidence_packet: EvidencePacket
    ) -> str:
        result = validate_answer(final_content, evidence_packet.items)
        if result.unknown_citations:
            final_content = remove_unknown_citations(final_content, result)
            logger.warning(
                "unknown_citations_removed count=%s",
                len(result.unknown_citations),
            )
        if result.missing_citation_despite_evidence:
            logger.warning("citation_missing repair_skipped=latency_policy")

        grounding_checks = assess_citation_grounding(
            final_content, evidence_packet.items
        )
        if grounding_checks:
            low_grounding = [c for c in grounding_checks if c.low_grounding]
            logger.info(
                "citation_grounding_checked citations=%s low_grounding=%s "
                "min_overlap=%s",
                len(grounding_checks),
                len(low_grounding),
                min(c.overlap_ratio for c in grounding_checks),
            )
            for check in low_grounding:
                logger.warning(
                    "citation_grounding_low citation=%s overlap_ratio=%s",
                    check.citation,
                    check.overlap_ratio,
                )
        return final_content

    async def aclose(self) -> None:
        close = getattr(self.model_client, "aclose", None)
        if close is not None:
            await close()
