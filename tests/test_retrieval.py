from __future__ import annotations

import asyncio
import json
import unittest

from mcp import MCPError

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


class SessionTerminatedGateway(RecordingGateway):
    tool_attempts = 0

    async def call_tool(self, name, arguments):
        self.__class__.tool_attempts += 1
        if self.__class__.tool_attempts == 1:
            raise MCPError(-32000, "Session terminated")
        return await super().call_tool(name, arguments)


class ParallelGateway(RecordingGateway):
    def __init__(self, settings) -> None:
        super().__init__(settings)
        self.active = 0
        self.max_active = 0
        self.both_started = asyncio.Event()

    async def call_tool(self, name, arguments):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        if self.active >= 2:
            self.both_started.set()
        try:
            await asyncio.wait_for(self.both_started.wait(), timeout=0.2)
            return await super().call_tool(name, arguments)
        finally:
            self.active -= 1


class RetrievalTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        RecordingGateway.instances.clear()
        SessionTerminatedGateway.instances.clear()
        SessionTerminatedGateway.tool_attempts = 0

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
        self.assertEqual(model.calls[0]["tool_choice"], "required")

    async def test_valid_finalize_skips_pending_calls_from_same_round(
        self,
    ) -> None:
        model = SequenceModel(
            [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call(
                            "call-1", "fake_search", {"query": "second"}
                        )
                    ],
                },
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call(
                            "call-2", "fake_search", {"query": "unused"}
                        ),
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
                        ),
                    ],
                },
            ]
        )
        runner = RetrievalRunner(
            make_settings(),
            model,
            gateway_factory=RecordingGateway,
        )

        result = await runner.run("test query")

        self.assertEqual(result.status, "sufficient")
        self.assertEqual(
            RecordingGateway.instances[0].calls,
            [("fake_search", {"query": "second"})],
        )
        self.assertEqual(model.calls[1]["tool_choice"], "required")

    async def test_invalid_finalize_does_not_skip_valid_pending_call(
        self,
    ) -> None:
        model = SequenceModel(
            [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call(
                            "call-1", "fake_search", {"query": "second"}
                        ),
                        tool_call(
                            "call-2",
                            "finalize_retrieval",
                            {"items": []},
                        ),
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
        runner = RetrievalRunner(
            make_settings(),
            model,
            gateway_factory=RecordingGateway,
        )

        result = await runner.run("test query")

        self.assertEqual(result.status, "sufficient")
        self.assertEqual(
            RecordingGateway.instances[0].calls,
            [("fake_search", {"query": "second"})],
        )

    async def test_no_tool_response_keeps_repair_fallback(self) -> None:
        model = SequenceModel(
            [
                {"role": "assistant", "content": "I will search."},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call(
                            "call-1",
                            "finalize_retrieval",
                            {"status": "no_evidence", "items": []},
                        )
                    ],
                },
            ]
        )
        runner = RetrievalRunner(
            make_settings(),
            model,
            gateway_factory=RecordingGateway,
        )

        result = await runner.run("test query")

        self.assertEqual(result.status, "no_evidence")
        self.assertEqual(len(model.calls), 2)
        self.assertEqual(model.calls[0]["tool_choice"], "required")
        self.assertIn(
            "Continue retrieval",
            model.calls[1]["messages"][-1]["content"],
        )

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

    async def test_finalize_role_tag_propagates_to_resolved_evidence(self) -> None:
        model = SequenceModel(
            [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call(
                            "call-1", "fake_search", {"query": "second"}
                        )
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
                                        "cite_uid": "cite-context-1",
                                        "relevance_score": 1.0,
                                        "role": "caveat",
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
            gateway_factory=RecordingGateway,
        )

        result = await runner.run("test query")

        self.assertEqual(result.evidence[0].role, "caveat")

    async def test_session_terminated_tool_call_reopens_gateway_once(self) -> None:
        model = SequenceModel(
            [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call(
                            "call-1", "fake_search", {"query": "second"}
                        )
                    ],
                },
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call(
                            "call-2", "fake_search", {"query": "second"}
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
        runner = RetrievalRunner(
            make_settings(),
            model,
            gateway_factory=SessionTerminatedGateway,
        )

        result = await runner.run("test query")

        self.assertEqual(result.status, "sufficient")
        self.assertEqual(SessionTerminatedGateway.tool_attempts, 2)
        self.assertEqual(len(SessionTerminatedGateway.instances), 2)

    async def test_tool_calls_from_one_model_round_run_concurrently(self) -> None:
        model = SequenceModel(
            [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call("call-1", "fake_search", {"query": "one"}),
                        tool_call("call-2", "fake_search", {"query": "two"}),
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
            make_settings(),
            model,
            gateway_factory=ParallelGateway,
        )

        result = await runner.run("parallel query")

        gateway = ParallelGateway.instances[-1]
        self.assertEqual(result.status, "no_evidence")
        self.assertEqual(gateway.max_active, 2)
        self.assertEqual(len(gateway.calls), 2)


if __name__ == "__main__":
    unittest.main()
