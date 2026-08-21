from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from mcp import MCPError
from pydantic import ValidationError

from src.config import Settings
from src.evidence import EvidenceRegistry
from src.mcp_gateway import MCPGateway
from src.prompts import RETRIEVAL_SYSTEM_PROMPT
from src.schemas import CitationSelection, RetrievalEnvelope
from src.tooling import (
    FINALIZE_TOOL,
    assistant_message_for_history,
    parse_tool_arguments,
    tool_call_name,
    tool_error_content,
    tool_result_message,
    validated_tool_calls,
)


logger = logging.getLogger(__name__)


class RetrievalRunner:
    def __init__(
        self,
        settings: Settings,
        model_client: Any,
        gateway_factory: Callable[[Settings], Any] = MCPGateway,
    ) -> None:
        self.settings = settings
        self.model_client = model_client
        self.gateway_factory = gateway_factory

    async def run(
        self, query: str, *, _retried_session: bool = False
    ) -> RetrievalEnvelope:
        query = query.strip()
        if not query:
            return RetrievalEnvelope(
                status="no_evidence",
                note="Retrieval query was empty.",
            )

        registry = EvidenceRegistry(self.settings.max_evidence_chars)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": RETRIEVAL_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        mcp_call_count = 0

        try:
            async with self.gateway_factory(self.settings) as gateway:
                mcp_tools = await gateway.list_openai_tools()
                allowed_names = {
                    tool["function"]["name"]
                    for tool in mcp_tools
                    if isinstance(tool.get("function"), dict)
                }

                for round_index in range(
                    self.settings.max_retrieval_model_rounds
                ):
                    force_finalize = (
                        mcp_call_count >= self.settings.max_retrieval_mcp_calls
                        or round_index
                        == self.settings.max_retrieval_model_rounds - 1
                    )
                    tools = [FINALIZE_TOOL] if force_finalize else [
                        *mcp_tools,
                        FINALIZE_TOOL,
                    ]
                    tool_choice: dict[str, Any] | None = None
                    if force_finalize:
                        tool_choice = {
                            "type": "function",
                            "function": {"name": "finalize_retrieval"},
                        }

                    assistant = await self.model_client.chat(
                        messages,
                        tools=tools,
                        tool_choice=tool_choice,
                    )
                    calls = validated_tool_calls(assistant)
                    messages.append(assistant_message_for_history(assistant))

                    if not calls:
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "Do not answer the user. Continue retrieval or call "
                                    "finalize_retrieval now."
                                ),
                            }
                        )
                        continue

                    for call in calls:
                        name = tool_call_name(call)
                        try:
                            arguments = parse_tool_arguments(call)
                        except (ValueError, json.JSONDecodeError) as exc:
                            self._append_tool_error(
                                messages,
                                call,
                                name or "unknown_tool",
                                f"Invalid JSON arguments: {exc}",
                            )
                            continue

                        if name == "finalize_retrieval":
                            try:
                                selection = CitationSelection.model_validate(arguments)
                            except ValidationError as exc:
                                self._append_tool_error(
                                    messages,
                                    call,
                                    name,
                                    f"Invalid finalize_retrieval payload: {exc.title}",
                                )
                                continue
                            return registry.resolve(selection)

                        if name not in allowed_names:
                            self._append_tool_error(
                                messages,
                                call,
                                name or "unknown_tool",
                                "Tool is not in the live MCP allowlist.",
                            )
                            continue

                        if (
                            mcp_call_count
                            >= self.settings.max_retrieval_mcp_calls
                        ):
                            self._append_tool_error(
                                messages,
                                call,
                                name,
                                "Retrieval tool-call budget is exhausted.",
                            )
                            continue

                        try:
                            payload, content = await gateway.call_tool(
                                name, arguments
                            )
                        except Exception as exc:
                            logger.warning(
                                "mcp_tool_failed tool=%s error_type=%s",
                                name,
                                type(exc).__name__,
                            )
                            self._append_tool_error(
                                messages,
                                call,
                                name,
                                f"MCP tool failed: {type(exc).__name__}",
                            )
                            mcp_call_count += 1
                            continue

                        if payload.get("isError") is not True:
                            registry.capture(name, payload)
                        mcp_call_count += 1
                        try:
                            messages.append(
                                tool_result_message(call, name, content)
                            )
                        except ValueError:
                            logger.warning("mcp_tool_call_missing_id tool=%s", name)

        except Exception as exc:
            if (
                not _retried_session
                and isinstance(exc, MCPError)
                and "Session terminated" in str(exc)
            ):
                logger.info("mcp_session_terminated retrying_retrieval=true")
                return await self.run(query, _retried_session=True)
            logger.warning(
                "retrieval_failed error_type=%s", type(exc).__name__
            )
            return RetrievalEnvelope(
                status="no_evidence",
                note=f"Retrieval was unavailable ({type(exc).__name__}).",
            )

        return RetrievalEnvelope(
            status="no_evidence",
            note="Retrieval ended without a valid finalize_retrieval call.",
        )

    @staticmethod
    def _append_tool_error(
        messages: list[dict[str, Any]],
        call: dict[str, Any],
        name: str,
        error: str,
    ) -> None:
        try:
            messages.append(
                tool_result_message(call, name, tool_error_content(error))
            )
        except ValueError:
            logger.warning("invalid_tool_call_without_id tool=%s", name)
