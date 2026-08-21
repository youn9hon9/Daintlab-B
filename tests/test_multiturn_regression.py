from __future__ import annotations

import json
import unittest

from src.driver import Driver
from src.schemas import InputMessage
from tests.helpers import SequenceModel, make_settings


class MultiturnRegressionTest(unittest.IsolatedAsyncioTestCase):
    async def test_red_flag_persists_and_pronoun_resolves_across_three_turns(
        self,
    ) -> None:
        # Turn 1: vague but concerning symptom -> expect a red flag in this
        # call's Generation payload.
        model1 = SequenceModel(
            [{"role": "assistant", "content": "가슴 답답 증상에 대한 안내 답변"}]
        )
        driver1 = Driver(make_settings(), model_client=model1)
        history: list[InputMessage] = [
            InputMessage(
                role="user",
                content="며칠 전부터 가슴이 답답하고 조이는 느낌이 있어요",
            )
        ]
        answer1 = await driver1.generate(history)
        history.append(InputMessage(role="assistant", content=answer1))

        payload1 = json.loads(model1.calls[0]["messages"][-1]["content"])
        self.assertIn(
            "chest_pain_cardiac", payload1["risk_flags"]["active_categories"]
        )
        self.assertIn("response_guidance", payload1)
        self.assertFalse(payload1["response_guidance"]["clarification_needed"])

        # Turn 2: user downplays/reassures -> the turn-1 flag must still be
        # present, and reassurance_detected must be set.
        model2 = SequenceModel(
            [
                {
                    "role": "assistant",
                    "content": "안심되시더라도 주의가 필요한 이유를 설명한 답변",
                }
            ]
        )
        driver2 = Driver(make_settings(), model_client=model2)
        history.append(
            InputMessage(role="user", content="그냥 별거 아니겠죠? 오늘은 좀 괜찮아요")
        )
        answer2 = await driver2.generate(history)
        history.append(InputMessage(role="assistant", content=answer2))

        payload2 = json.loads(model2.calls[0]["messages"][-1]["content"])
        self.assertIn(
            "chest_pain_cardiac", payload2["risk_flags"]["active_categories"]
        )
        self.assertTrue(payload2["risk_flags"]["reassurance_detected"])

        # Turn 3: pronoun follow-up ("그 증상") -> single L2 call still
        # carries the flag from turn 1.
        model3 = SequenceModel(
            [
                {
                    "role": "assistant",
                    "content": "그 증상은 계속 주의 관찰이 필요하다는 최종 답변",
                }
            ]
        )
        driver3 = Driver(make_settings(), model_client=model3)
        history.append(
            InputMessage(role="user", content="그 증상은 계속 지켜보면 될까요?")
        )
        await driver3.generate(history)

        payload3 = json.loads(model3.calls[0]["messages"][-1]["content"])
        self.assertIn(
            "chest_pain_cardiac", payload3["risk_flags"]["active_categories"]
        )
        self.assertEqual(len(model3.calls), 1)


if __name__ == "__main__":
    unittest.main()
