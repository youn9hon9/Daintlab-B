from __future__ import annotations

import json
import unittest

from src.context import CONTEXT_CHAR_LIMIT, build_oneshot_input
from src.driver import Driver
from src.errors import UpstreamProtocolError
from src.prompts import ONESHOT_SYSTEM_PROMPT
from src.schemas import InputMessage
from tests.helpers import SequenceModel, make_settings


class OneShotDriverTest(unittest.IsolatedAsyncioTestCase):
    async def test_exactly_one_call_without_tools_or_retry(self) -> None:
        model = SequenceModel(
            [{"role": "assistant", "content": "완결된 답변"}]
        )
        driver = Driver(make_settings(), model_client=model)

        answer = await driver.generate(
            [InputMessage(role="user", content="두통이 사흘째예요.")]
        )

        self.assertEqual(answer, "완결된 답변")
        self.assertEqual(len(model.calls), 1)
        self.assertIsNone(model.calls[0]["tools"])
        self.assertIsNone(model.calls[0]["tool_choice"])
        self.assertEqual(model.calls[0]["max_retries"], 0)
        self.assertEqual(model.calls[0]["max_tokens"], 768)

    async def test_reasoning_only_response_is_rejected(self) -> None:
        model = SequenceModel(
            [
                {
                    "role": "assistant",
                    "content": "",
                    "reasoning_content": "internal reasoning",
                    "_finish_reason": "length",
                }
            ]
        )
        driver = Driver(make_settings(), model_client=model)

        with self.assertRaisesRegex(UpstreamProtocolError, "empty message.content"):
            await driver.generate(
                [InputMessage(role="user", content="질문")]
            )

        self.assertEqual(len(model.calls), 1)

    async def test_current_question_is_not_truncated(self) -> None:
        question = "현재 질문 " + ("가" * 2_000)
        model = SequenceModel([{"role": "assistant", "content": "답변"}])
        driver = Driver(make_settings(), model_client=model)

        await driver.generate([InputMessage(role="user", content=question)])

        payload = json.loads(model.calls[0]["messages"][1]["content"])
        self.assertEqual(payload["current_question"], question)


class ContextBudgetTest(unittest.TestCase):
    def test_preserves_clinical_context_and_drops_greetings(self) -> None:
        latest, context = build_oneshot_input(
            [
                InputMessage(role="user", content="안녕하세요"),
                InputMessage(role="user", content="45세 여성이고 고혈압 약을 복용해요."),
                InputMessage(role="assistant", content="무엇이 궁금한가요?"),
                InputMessage(role="user", content="두통이 3일째인데 관련 있나요?"),
            ]
        )

        self.assertEqual(latest, "두통이 3일째인데 관련 있나요?")
        self.assertIn("45세 여성", context)
        self.assertNotIn("안녕하세요", context)
        self.assertLessEqual(len(context), CONTEXT_CHAR_LIMIT)

    def test_keeps_referenced_assistant_content(self) -> None:
        _, context = build_oneshot_input(
            [
                InputMessage(role="assistant", content="검사 결과를 확인하세요."),
                InputMessage(role="user", content="아까 말한 그 검사는 언제 하나요?"),
            ]
        )

        self.assertIn("검사 결과", context)

    def test_system_prompt_stays_under_budget(self) -> None:
        self.assertLessEqual(len(ONESHOT_SYSTEM_PROMPT), 1_200)


if __name__ == "__main__":
    unittest.main()
