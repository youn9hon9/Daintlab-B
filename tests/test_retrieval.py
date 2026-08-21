from __future__ import annotations

import json
import unittest

from src.retrieval import RetrievalRunner
from tests.helpers import SequenceModel, make_settings, tool_call


class ErrorGateway:
    def __init__(self, settings) -> None:
        self.settings = settings

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def list_openai_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "failing_search",
                    "description": "Always fails.",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

    async def call_tool(self, name, arguments):
        payload = {
            "content": [
                {
                    "type": "text",
                    "text": 'error mentions cite_uid "cite-error-1"',
                }
            ],
            "isError": True,
        }
        return payload, json.dumps(payload)


class RecordingGateway:
    instances = []

    def __init__(self, settings) -> None:
        self.settings = settings
        self.calls = []
        self.__class__.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def list_openai_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "fake_search",
                    "description": "Search test evidence.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                    },
                },
            }
        ]

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        query = arguments.get("query", "")
        if query == "first":
            payload = {"isError": False, "content": "a" * 90}
            return payload, "a" * 90

        item = {
            "cite_uid": "cite-context-1",
            "content": "relevant evidence " + "b" * 300,
        }
        payload = {"isError": False, "structuredContent": item}
        return payload, json.dumps(payload, ensure_ascii=False)


class RetrievalTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        RecordingGateway.instances.clear()

    async def test_error_tool_result_cannot_be_selected_as_evidence(self) -> None:
        model = SequenceModel(
            [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call("call-1", "failing_search", {})
                    ],
                },
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call(
                            "call-2",
                            "finalize_retrieval",
                            {
                                "status": "sufficient",
                                "items": [
                                    {
                                        "cite_uid": "cite-error-1",
                                        "relevance_score": 1.0,
                                    }
                                ],
                            },
                        )
                    ],
                },
            ]
        )
        runner = RetrievalRunner(
            make_settings(),
            model,
            gateway_factory=ErrorGateway,
        )

        result = await runner.run("test query")

        self.assertEqual(result.status, "no_evidence")
        self.assertEqual(result.evidence, [])

    async def test_duplicate_call_is_skipped_and_forces_finalize(self) -> None:
        model = SequenceModel(
            [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call(
                            "call-1",
                            "fake_search",
                            {"query": "same", "limit": 2},
                        )
                    ],
                },
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call(
                            "call-2",
                            "fake_search",
                            {"limit": 2, "query": "same"},
                        )
                    ],
                },
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call(
                            "call-3",
                            "finalize_retrieval",
                            {"status": "no_evidence", "items": []},
                        )
                    ],
                },
            ]
        )
        runner = RetrievalRunner(
            make_settings(max_retrieval_mcp_calls=4),
            model,
            gateway_factory=RecordingGateway,
        )

        result = await runner.run("test query")

        self.assertEqual(result.status, "no_evidence")
        self.assertEqual(len(RecordingGateway.instances[0].calls), 1)
        duplicate_result = model.calls[2]["messages"][-1]
        self.assertEqual(duplicate_result["role"], "tool")
        self.assertTrue(json.loads(duplicate_result["content"])["isError"])
        self.assertEqual(
            model.calls[2]["tool_choice"]["function"]["name"],
            "finalize_retrieval",
        )

    async def test_tool_result_context_has_global_limit_and_keeps_uid(self) -> None:
        model = SequenceModel(
            [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call("call-1", "fake_search", {"query": "first"})
                    ],
                },
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call("call-2", "fake_search", {"query": "second"})
                    ],
                },
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call(
                            "call-3",
                            "finalize_retrieval",
                            {
                                "status": "sufficient",
                                "items": [
                                    {
                                        "cite_uid": "cite-context-1",
                                        "relevance_score": 1.0,
                                    }
                                ],
                            },
                        )
                    ],
                },
            ]
        )
        settings = make_settings(max_retrieval_context_chars=220)
        runner = RetrievalRunner(
            settings,
            model,
            gateway_factory=RecordingGateway,
        )

        result = await runner.run("test query")

        tool_contents = [
            message["content"]
            for message in model.calls[2]["messages"]
            if message["role"] == "tool"
        ]
        self.assertLessEqual(sum(map(len, tool_contents)), 220)
        self.assertIn("cite-context-1", tool_contents[-1])
        self.assertEqual(result.status, "sufficient")
        self.assertEqual(result.evidence[0].cite_uid, "cite-context-1")


if __name__ == "__main__":
    unittest.main()
