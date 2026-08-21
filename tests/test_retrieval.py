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


class RetrievalTest(unittest.IsolatedAsyncioTestCase):
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


if __name__ == "__main__":
    unittest.main()
