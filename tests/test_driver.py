from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import patch

from src.driver import Driver
from src.errors import UpstreamProtocolError
from src.schemas import InputMessage
from tests.helpers import (
    FakeGatewayFactory,
    SequenceModel,
    make_settings,
    tool_call,
)


class SlowRetrievalRunner:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def run(self, query: str, *, deadline: float | None = None):
        await asyncio.sleep(0.1)


class DriverTest(unittest.IsolatedAsyncioTestCase):
    async def test_direct_generation_without_retrieval(self) -> None:
        model = SequenceModel(
            [{"role": "assistant", "content": "직접 생성한 L2 답변"}]
        )
        driver = Driver(make_settings(), model_client=model)

        answer = await driver.generate(
            [InputMessage(role="user", content="일반적인 건강 질문")]
        )

        self.assertEqual(answer, "직접 생성한 L2 답변")
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(
            model.calls[0]["tools"][0]["function"]["name"],
            "retrieve_relevant_content",
        )
        self.assertEqual(model.calls[0]["phase"], "initial")

    async def test_generation_retrieval_generation_flow(self) -> None:
        model = SequenceModel(
            [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call(
                            "generation-1",
                            "retrieve_relevant_content",
                            {"query": "완결된 임상 가이드라인 질문"},
                        )
                    ],
                },
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call(
                            "retrieval-1",
                            "fake_search",
                            {"query": "guideline evidence"},
                        )
                    ],
                },
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call(
                            "retrieval-2",
                            "finalize_retrieval",
                            {
                                "status": "sufficient",
                                "items": [
                                    {
                                        "cite_uid": "cite-test-1",
                                        "relevance_score": 0.95,
                                    }
                                ],
                                "note": "",
                            },
                        )
                    ],
                },
                {
                    "role": "assistant",
                    "content": "근거 기반 최종 답변 [1]",
                },
            ]
        )
        gateways = FakeGatewayFactory()
        driver = Driver(
            make_settings(),
            model_client=model,
            gateway_factory=gateways,
        )

        answer = await driver.generate(
            [
                InputMessage(role="user", content="이 질환의 목표는?"),
                InputMessage(role="assistant", content="질환을 알려주세요."),
                InputMessage(role="user", content="아까 그 질환이요."),
            ]
        )

        self.assertEqual(answer, "근거 기반 최종 답변 [1]")
        self.assertEqual(len(gateways.instances), 1)
        self.assertEqual(
            gateways.instances[0].calls,
            [("fake_search", {"query": "guideline evidence"})],
        )
        generation_resume = model.calls[-1]["messages"][-1]
        self.assertEqual(generation_resume["role"], "tool")
        envelope = json.loads(generation_resume["content"])
        self.assertEqual(envelope["status"], "sufficient")
        self.assertEqual(envelope["evidence"][0]["citation"], "[1]")
        self.assertEqual(
            envelope["evidence"][0]["cite_uid"], "cite-test-1"
        )
        self.assertEqual(model.calls[-1]["phase"], "final")
        self.assertIsNone(model.calls[-1]["tools"])
        self.assertEqual(model.calls[-1]["max_retries"], 1)

    async def test_malformed_tool_call_is_rejected_before_round_trip(self) -> None:
        model = SequenceModel(
            [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {
                                "name": "retrieve_relevant_content",
                                "arguments": "{}",
                            },
                        }
                    ],
                }
            ]
        )
        driver = Driver(make_settings(), model_client=model)

        with self.assertRaises(UpstreamProtocolError):
            await driver.generate(
                [InputMessage(role="user", content="근거가 필요한 질문")]
            )

    async def test_retrieval_timeout_preserves_final_generation(self) -> None:
        model = SequenceModel(
            [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call(
                            "generation-1",
                            "retrieve_relevant_content",
                            {"query": "slow evidence query"},
                        )
                    ],
                },
                {
                    "role": "assistant",
                    "content": "검색 시간 제한을 반영한 최종 답변",
                },
            ]
        )
        settings = make_settings(
            request_timeout_seconds=1.0,
            retrieval_timeout_seconds=0.01,
            final_generation_reserve_seconds=0.2,
        )
        driver = Driver(settings, model_client=model)

        with patch("src.driver.RetrievalRunner", SlowRetrievalRunner):
            answer = await driver.generate(
                [InputMessage(role="user", content="근거가 필요한 질문")]
            )

        self.assertEqual(answer, "검색 시간 제한을 반영한 최종 답변")
        tool_message = model.calls[-1]["messages"][-1]
        self.assertEqual(tool_message["role"], "tool")
        self.assertEqual(json.loads(tool_message["content"])["status"], "no_evidence")
        self.assertEqual(model.calls[-1]["phase"], "final")
        self.assertIsNone(model.calls[-1]["tools"])
        self.assertEqual(model.calls[-1]["max_retries"], 1)


if __name__ == "__main__":
    unittest.main()
