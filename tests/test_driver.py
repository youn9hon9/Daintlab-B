from __future__ import annotations

import json
import unittest

from src.driver import Driver
from src.errors import UpstreamProtocolError
from src.schemas import InputMessage
from tests.helpers import (
    FakeGatewayFactory,
    SequenceModel,
    make_settings,
    tool_call,
)


class DriverTest(unittest.IsolatedAsyncioTestCase):
    async def test_direct_route_makes_exactly_one_l2_call_with_no_tools(
        self,
    ) -> None:
        model = SequenceModel(
            [{"role": "assistant", "content": "직접 생성한 답변"}]
        )
        driver = Driver(make_settings(), model_client=model)

        answer = await driver.generate(
            [InputMessage(role="user", content="일반적인 건강 질문입니다")]
        )

        self.assertEqual(answer, "직접 생성한 답변")
        self.assertEqual(len(model.calls), 1)
        self.assertIsNone(model.calls[0]["tools"])
        self.assertEqual(model.calls[0]["max_retries"], 0)
        payload = json.loads(model.calls[0]["messages"][-1]["content"])
        self.assertNotIn("evidence", payload)

    async def test_evidence_route_compiles_evidence_before_the_single_l2_call(
        self,
    ) -> None:
        model = SequenceModel(
            [{"role": "assistant", "content": "근거 기반 답변 [1]"}]
        )
        gateways = FakeGatewayFactory()
        driver = Driver(
            make_settings(), model_client=model, gateway_factory=gateways
        )

        answer = await driver.generate(
            [
                InputMessage(
                    role="user",
                    content="이 약의 허가 용량과 금기를 확인해 주세요",
                )
            ]
        )

        self.assertEqual(answer, "근거 기반 답변 [1]")
        self.assertEqual(len(model.calls), 1)
        self.assertIsNone(model.calls[0]["tools"])
        payload = json.loads(model.calls[0]["messages"][-1]["content"])
        self.assertIn("evidence", payload)
        self.assertEqual(payload["evidence"]["items"][0]["citation"], "[1]")
        self.assertEqual(len(gateways.instances), 1)
        self.assertEqual(
            gateways.instances[0].calls[0][0],
            "openapi_mfds_get_drug_indication",
        )

    async def test_mcp_failure_falls_back_to_direct_generation(self) -> None:
        class FailingGatewayFactory:
            def __call__(self, settings):
                raise ConnectionError("MCP unreachable")

        model = SequenceModel(
            [{"role": "assistant", "content": "검색 없이 작성한 답변"}]
        )
        driver = Driver(
            make_settings(),
            model_client=model,
            gateway_factory=FailingGatewayFactory(),
        )

        answer = await driver.generate(
            [
                InputMessage(
                    role="user",
                    content="이 약의 허가 용량과 금기를 확인해 주세요",
                )
            ]
        )

        self.assertEqual(answer, "검색 없이 작성한 답변")
        self.assertEqual(len(model.calls), 1)
        payload = json.loads(model.calls[0]["messages"][-1]["content"])
        self.assertNotIn("evidence", payload)

    async def test_unexpected_tool_call_is_rejected(self) -> None:
        model = SequenceModel(
            [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call("call-1", "retrieve_relevant_content", {})
                    ],
                }
            ]
        )
        driver = Driver(make_settings(), model_client=model)

        with self.assertRaises(UpstreamProtocolError):
            await driver.generate(
                [InputMessage(role="user", content="일반적인 질문")]
            )

    async def test_empty_content_is_not_treated_as_success(self) -> None:
        model = SequenceModel([{"role": "assistant", "content": ""}])
        driver = Driver(make_settings(), model_client=model)

        with self.assertRaises(UpstreamProtocolError):
            await driver.generate(
                [InputMessage(role="user", content="일반적인 질문")]
            )

    async def test_reasoning_content_never_becomes_the_answer(self) -> None:
        model = SequenceModel(
            [
                {
                    "role": "assistant",
                    "content": "보이는 답변만 사용",
                    "reasoning_content": "내부 추론 과정, 노출되면 안 됨",
                }
            ]
        )
        driver = Driver(make_settings(), model_client=model)

        answer = await driver.generate(
            [InputMessage(role="user", content="일반적인 질문")]
        )

        self.assertEqual(answer, "보이는 답변만 사용")
        self.assertNotIn("내부 추론", answer)

    async def test_unknown_citation_is_removed_from_evidence_route_answer(
        self,
    ) -> None:
        model = SequenceModel(
            [{"role": "assistant", "content": "근거 [1][9] 기반 답변"}]
        )
        driver = Driver(
            make_settings(),
            model_client=model,
            gateway_factory=FakeGatewayFactory(),
        )

        answer = await driver.generate(
            [
                InputMessage(
                    role="user",
                    content="이 약의 허가 용량과 금기를 확인해 주세요",
                )
            ]
        )

        self.assertEqual(answer, "근거 [1] 기반 답변")


if __name__ == "__main__":
    unittest.main()
