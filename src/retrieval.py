from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from mcp import MCPError
from pydantic import ValidationError

from src.config import Settings
from src.evidence import EvidenceRegistry, extract_cite_uids
from src.mcp_gateway import MCPGateway
from src.prompts import RETRIEVAL_SYSTEM_PROMPT
from src.retrieval_tools import select_retrieval_tools
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

        registry = EvidenceRegistry(
            self.settings.max_evidence_chars,
            max_items=getattr(self.settings, "max_selected_evidence", None),
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": RETRIEVAL_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        mcp_call_count = 0
        context_chars_used = 0
        context_char_limit = getattr(
            self.settings,
            "max_retrieval_context_chars",
            self.settings.max_mcp_result_chars
            * self.settings.max_retrieval_mcp_calls,
        )
        seen_mcp_calls: set[tuple[str, str]] = set()
        force_finalize_next = False

        try:
            async with self.gateway_factory(self.settings) as gateway:
                live_tools = await gateway.list_openai_tools()
                mcp_tools = select_retrieval_tools(
                    query,
                    live_tools,
                    limit=self.settings.max_retrieval_tools,
                )
                allowed_names = {
                    tool["function"]["name"]
                    for tool in mcp_tools
                    if isinstance(tool.get("function"), dict)
                }
                logger.info(
                    "retrieval_started selected_tools=%s",
                    ",".join(sorted(allowed_names)),
                )

                for round_index in range(
                    self.settings.max_retrieval_model_rounds
                ):
                    force_finalize = (
                        force_finalize_next
                        or mcp_call_count
                        >= self.settings.max_retrieval_mcp_calls
                        or context_chars_used >= context_char_limit
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

                    pending_calls: list[
                        tuple[dict[str, Any], str, dict[str, Any]]
                    ] = []
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
                            mcp_call_count + len(pending_calls)
                            >= self.settings.max_retrieval_mcp_calls
                        ):
                            self._append_tool_error(
                                messages,
                                call,
                                name,
                                "Retrieval tool-call budget is exhausted.",
                            )
                            continue

                        call_key = (
                            name,
                            json.dumps(
                                arguments,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                        )
                        if call_key in seen_mcp_calls:
                            self._append_tool_error(
                                messages,
                                call,
                                name,
                                (
                                    "Duplicate MCP tool call was skipped. "
                                    "Use the existing result and finalize retrieval."
                                ),
                            )
                            mcp_call_count += 1
                            force_finalize_next = True
                            continue

                        if context_chars_used >= context_char_limit:
                            self._append_tool_error(
                                messages,
                                call,
                                name,
                                (
                                    "Retrieval context budget is exhausted. "
                                    "Finalize retrieval with the evidence already gathered."
                                ),
                            )
                            mcp_call_count += 1
                            force_finalize_next = True
                            continue

                        seen_mcp_calls.add(call_key)
                        pending_calls.append((call, name, arguments))

                    if not pending_calls:
                        continue

                    mcp_call_count += len(pending_calls)
                    results = await asyncio.gather(
                        *(
                            gateway.call_tool(name, arguments)
                            for _, name, arguments in pending_calls
                        ),
                        return_exceptions=True,
                    )
                    for (call, name, _), result in zip(
                        pending_calls, results, strict=True
                    ):
                        if isinstance(result, BaseException):
                            logger.warning(
                                "mcp_tool_failed tool=%s error_type=%s",
                                name,
                                type(result).__name__,
                            )
                            self._append_tool_error(
                                messages,
                                call,
                                name,
                                f"MCP tool failed: {type(result).__name__}",
                            )
                            continue

                        payload, content = result
                        if payload.get("isError") is not True:
                            registry.capture(name, payload)
                        remaining_context_chars = max(
                            0, context_char_limit - context_chars_used
                        )
                        content = self._bounded_context_content(
                            content,
                            payload,
                            remaining_context_chars,
                        )
                        context_chars_used += len(content)
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

    @staticmethod
    def _bounded_context_content(
        content: str,
        payload: Any,
        limit: int,
    ) -> str:
        if limit <= 0:
            return ""
        if len(content) <= limit:
            return content

        cite_uids = extract_cite_uids(payload)
        compact = {
            "truncated": True,
            "original_chars": len(content),
            "cite_uids": cite_uids,
        }
        encoded = json.dumps(
            compact,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if len(encoded) > limit:
            uid_only = json.dumps(
                {"cite_uids": cite_uids},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            if len(uid_only) <= limit:
                return uid_only

            raw_uids = "\n".join(cite_uids)
            if raw_uids and len(raw_uids) <= limit:
                return raw_uids
            return (raw_uids or content)[:limit]

        low = 0
        high = max(0, (limit - len(encoded)) // 2)
        best = encoded
        while low <= high:
            excerpt_size = (low + high) // 2
            candidate = {
                **compact,
                "content_prefix": content[:excerpt_size],
                "content_suffix": content[-excerpt_size:]
                if excerpt_size
                else "",
            }
            candidate_encoded = json.dumps(
                candidate,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            if len(candidate_encoded) <= limit:
                best = candidate_encoded
                low = excerpt_size + 1
            else:
                high = excerpt_size - 1
        return best
