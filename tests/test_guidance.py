from __future__ import annotations

import unittest

from src.guidance import assess_response_guidance
from src.safety import assess_risk
from src.schemas import InputMessage


def assess(*contents: str):
    history = [InputMessage(role="user", content=content) for content in contents]
    return assess_response_guidance(history, assess_risk(history))


class ResponseGuidanceTest(unittest.TestCase):
    def test_personal_symptom_question_requests_missing_context(self) -> None:
        result = assess("제가 머리가 아픈데 병원에 가야 하나요?")
        self.assertTrue(result.clarification_needed)
        self.assertIn("onset_or_duration", result.missing_context)
        self.assertIn("severity_or_trajectory", result.missing_context)

    def test_context_from_previous_turn_is_not_requested_again(self) -> None:
        result = assess(
            "저는 35세이고 고혈압약을 복용 중이에요.",
            "어제부터 약간 머리가 아픈데 병원에 가야 하나요?",
        )
        self.assertNotIn("age_group", result.missing_context)
        self.assertNotIn("relevant_conditions_or_medications", result.missing_context)
        self.assertFalse(result.clarification_needed)

    def test_emergency_action_overrides_clarification_gate(self) -> None:
        result = assess("제가 가슴이 조이고 숨쉬기 힘들어요")
        self.assertFalse(result.clarification_needed)
        self.assertIn("urgent action guidance", result.note)

    def test_global_access_question_requires_jurisdiction(self) -> None:
        result = assess("이 치료는 보험이 되고 어디서 받을 수 있나요?")
        self.assertTrue(result.global_context_needed)

    def test_named_jurisdiction_satisfies_global_context(self) -> None:
        result = assess("한국에서 이 치료는 보험이 되나요?")
        self.assertFalse(result.global_context_needed)

    def test_general_education_does_not_force_clarification(self) -> None:
        result = assess("비타민 D는 어떤 역할을 하나요?")
        self.assertFalse(result.clarification_needed)
        self.assertEqual(result.missing_context, [])


if __name__ == "__main__":
    unittest.main()
