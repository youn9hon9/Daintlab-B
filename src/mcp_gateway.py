from __future__ import annotations

import copy
import json
import logging
import time
from contextlib import AsyncExitStack
from types import TracebackType
from typing import Any

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from src.config import Settings
from src.evidence import extract_cite_uids
from src.errors import UpstreamProtocolError


logger = logging.getLogger(__name__)


class MCPGateway:
    _tool_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
    _tool_cache_ttl_seconds = 300.0

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._stack: AsyncExitStack | None = None
        self._client: Client | None = None
        self._allowed_tools: set[str] = set()

    async def __aenter__(self) -> "MCPGateway":
        api_key = self.settings.require_api_key()
        stack = AsyncExitStack()
        try:
            http_client = await stack.enter_async_context(
                httpx2.AsyncClient(
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=httpx2.Timeout(
                        self.settings.mcp_tool_timeout_seconds
                    ),
                    follow_redirects=True,
                )
            )
            transport = streamable_http_client(
                self.settings.lunit_mcp_url,
                http_client=http_client,
                terminate_on_close=self.settings.mcp_terminate_on_close,
            )
            self._client = await stack.enter_async_context(
                Client(
                    transport,
                    mode="auto",
                    read_timeout_seconds=self.settings.mcp_tool_timeout_seconds,
                )
            )
        except BaseException:
            await stack.aclose()
            raise
        self._stack = stack
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._stack is not None:
            await self._stack.aclose()

    def _require_client(self) -> Client:
        if self._client is None:
            raise RuntimeError("MCP gateway is not connected")
        return self._client

    async def list_openai_tools(self) -> list[dict[str, Any]]:
        cache_key = self.settings.lunit_mcp_url
        cached = self._tool_cache.get(cache_key)
        now = time.monotonic()
        if cached is not None and now - cached[0] < self._tool_cache_ttl_seconds:
            converted = copy.deepcopy(cached[1])
            self._allowed_tools.update(
                tool["function"]["name"]
                for tool in converted
                if isinstance(tool.get("function"), dict)
            )
            logger.info("mcp_tool_list_cache_hit tools=%s", len(converted))
            return converted

        client = self._require_client()
        tools: list[Any] = []
        cursor: str | None = None
        for _ in range(20):
            page = await client.list_tools(cursor=cursor)
            tools.extend(page.tools)
            cursor = page.next_cursor
            if cursor is None:
                break
        else:
            raise UpstreamProtocolError("MCP tools/list pagination did not finish")

        converted: list[dict[str, Any]] = []
        for tool in tools:
            if tool.name == "finalize_retrieval":
                continue
            self._allowed_tools.add(tool.name)
            converted.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or tool.title or "",
                        "parameters": tool.input_schema,
                    },
                }
            )
        self._tool_cache[cache_key] = (now, copy.deepcopy(converted))
        logger.info("mcp_tool_list_cache_miss tools=%s", len(converted))
        return converted

    @classmethod
    def clear_tool_cache(cls) -> None:
        cls._tool_cache.clear()

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        if name not in self._allowed_tools:
            raise ValueError(f"MCP tool is not allow-listed: {name}")
        client = self._require_client()
        result = await client.call_tool(
            name,
            arguments,
            read_timeout_seconds=self.settings.mcp_tool_timeout_seconds,
        )
        payload = result.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
        )
        raw_content = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        content = self._bounded_tool_content(raw_content, payload)
        return payload, content

    def _bounded_tool_content(self, raw_content: str, payload: Any) -> str:
        limit = self.settings.max_mcp_result_chars
        if len(raw_content) <= limit:
            return raw_content

        excerpt_size = max(128, limit // 4)
        cite_uids = extract_cite_uids(payload)
        for _ in range(8):
            compact = {
                "truncated": True,
                "original_chars": len(raw_content),
                "cite_uids": cite_uids,
                "content_prefix": raw_content[:excerpt_size],
                "content_suffix": raw_content[-excerpt_size:],
            }
            encoded = json.dumps(
                compact,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            if len(encoded) <= limit:
                return encoded
            excerpt_size //= 2

        return json.dumps(
            {
                "truncated": True,
                "original_chars": len(raw_content),
                "cite_uids": cite_uids[:20],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
