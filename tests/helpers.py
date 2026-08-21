from __future__ import annotations

import copy
import json
from typing import Any

from src.config import Settings


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "driver_model_id": "lunit-hackathon-driver",
        "lunit_fm_api_url": "https://model.example.test",
        "lunit_fm_api_key": "test-key",
        "lunit_fm_model": "Lunit/L2-preview",
        "lunit_mcp_url": "https://mcp.example.test/mcp",
        "upstream_timeout_seconds": 1.0,
        "request_timeout_seconds": 2.0,
        "final_generation_reserve_seconds": 0.5,
        "mcp_tool_timeout_seconds": 1.0,
        "mcp_terminate_on_close": False,
        "upstream_retries": 0,
        "upstream_concurrency": 2,
        "upstream_priority_slots": 0,
        "retry_base_seconds": 0.1,
        "retry_max_seconds": 1.0,
        "max_mcp_result_chars": 1000,
        "evidence_compiler_timeout_seconds": 1.0,
        "max_tokens_answer": 1024,
    }
    values.update(overrides)
    return Settings(**values)


class SequenceModel:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        phase: str = "initial",
        max_retries: int | None = None,
        retry_deadline: float | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "messages": copy.deepcopy(messages),
                "tools": copy.deepcopy(tools),
                "tool_choice": copy.deepcopy(tool_choice),
                "phase": phase,
                "max_retries": max_retries,
                "retry_deadline": retry_deadline,
            }
        )
        if not self.responses:
            raise AssertionError("Fake model has no response left")
        return copy.deepcopy(self.responses.pop(0))

    async def aclose(self) -> None:
        self.closed = True


_FAKE_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "index_get_relevant_nodes": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "corpus_tag": {"type": "string"},
        },
        "required": ["query"],
    },
    "openapi_mfds_get_drug_indication": {
        "type": "object",
        "properties": {"product_name": {"type": "string"}},
        "required": ["product_name"],
    },
    "openapi_law_search": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
    "openapi_law_get_article": {
        "type": "object",
        "properties": {"mst": {"type": "string"}},
        "required": ["mst"],
    },
}


class FakeGateway:
    """Exposes fake versions of the real MCP tool names F010's evidence
    compiler calls (index_get_relevant_nodes, openapi_mfds_get_drug_indication,
    openapi_law_search, openapi_law_get_article), each returning one
    cite_uid-bearing item so both single-hop and law-chain routes can be
    exercised in tests without a live MCP server.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def __aenter__(self) -> "FakeGateway":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def list_openai_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": "Fake tool for tests.",
                    "parameters": schema,
                },
            }
            for name, schema in _FAKE_TOOL_SCHEMAS.items()
        ]

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        self.calls.append((name, arguments))
        if name == "openapi_law_search":
            item = {"mst": "mst-test-1", "law_name": "Test Act"}
            payload = {"structuredContent": item, "isError": False}
            return payload, json.dumps(payload, ensure_ascii=False)
        item = {
            "cite_uid": f"cite-{name}-1",
            "title": "Test source",
            "date": "2026-01-01",
            "content": f"Verified test evidence from {name}.",
        }
        payload = {
            "content": [
                {"type": "text", "text": json.dumps(item, ensure_ascii=False)}
            ],
            "structuredContent": item,
            "isError": False,
        }
        return payload, json.dumps(payload, ensure_ascii=False)


class FakeGatewayFactory:
    def __init__(self) -> None:
        self.instances: list[FakeGateway] = []

    def __call__(self, settings: Settings) -> FakeGateway:
        gateway = FakeGateway(settings)
        self.instances.append(gateway)
        return gateway


def tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments, ensure_ascii=False),
        },
    }
