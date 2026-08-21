from __future__ import annotations

import unittest

from src.safety import assess_risk
from src.schemas import InputMessage


class SafetyTest(unittest.TestCase):
    def test_chest_pain_detected_in_first_user_turn(self) -> None:
        history = [
            InputMessage(role="user", content="어제부터 가슴이 조이는 느낌이 있어요")
        ]

        result = assess_risk(history)

        self.assertIn("chest_pain_cardiac", result.active_categories)
        self.assertTrue(result.has_risk)
        self.assertEqual(result.flags[0].turn_index, 0)

    def test_flag_persists_into_later_turn_without_repeating_keyword(self) -> None:
        history = [
            InputMessage(role="user", content="가슴이 조이고 답답해요"),
            InputMessage(role="assistant", content="언제부터 그러셨나요?"),
            InputMessage(
                role="user",
                content="그냥 별거 아니겠죠? 오늘은 좀 괜찮아진 것 같아요",
            ),
        ]

        result = assess_risk(history)

        self.assertIn("chest_pain_cardiac", result.active_categories)
        self.assertTrue(result.reassurance_detected)

    def test_no_flags_on_unrelated_question(self) -> None:
        result = assess_risk(
            [InputMessage(role="user", content="비타민 D는 언제 먹는 게 좋나요?")]
        )

        self.assertEqual(result.active_categories, [])
        self.assertFalse(result.has_risk)
        self.assertFalse(result.reassurance_detected)

    def test_assistant_messages_are_not_scanned(self) -> None:
        history = [
            InputMessage(role="user", content="비타민 D는 언제 먹는 게 좋나요?"),
            InputMessage(
                role="assistant",
                content="가슴 통증이 있다면 응급실에 가야 합니다.",
            ),
        ]

        result = assess_risk(history)

        self.assertFalse(result.has_risk)

    def test_multiple_categories_can_be_active_at_once(self) -> None:
        history = [
            InputMessage(
                role="user",
                content="가슴이 답답하고 숨쉬기도 힘들어요",
            )
        ]

        result = assess_risk(history)

        self.assertIn("chest_pain_cardiac", result.active_categories)
        self.assertIn("breathing_difficulty", result.active_categories)


if __name__ == "__main__":
    unittest.main()
