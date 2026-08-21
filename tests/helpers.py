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
        "retrieval_timeout_seconds": 1.0,
        "final_generation_reserve_seconds": 0.5,
        "mcp_tool_timeout_seconds": 1.0,
        "mcp_terminate_on_close": False,
        "upstream_retries": 0,
        "upstream_concurrency": 2,
        "upstream_priority_slots": 1,
        "retry_base_seconds": 0.1,
        "retry_max_seconds": 1.0,
        "max_generation_rounds": 3,
        "max_retrievals_per_answer": 1,
        "max_retrieval_model_rounds": 5,
        "max_retrieval_mcp_calls": 3,
        "max_mcp_result_chars": 1000,
        "max_retrieval_context_chars": 3000,
        "max_evidence_chars": 10_000,
        "max_selected_evidence": 3,
        "citation_repair_min_seconds": 0.5,
        "retrieval_enabled": True,
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


class FakeGateway:
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
                    "name": "fake_search",
                    "description": "Return citable test evidence.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            }
        ]

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        self.calls.append((name, arguments))
        item = {
            "cite_uid": "cite-test-1",
            "title": "Test guideline",
            "url": "https://example.test/guideline",
            "content": "Verified test evidence.",
        }
        payload = {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(item, ensure_ascii=False),
                }
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
