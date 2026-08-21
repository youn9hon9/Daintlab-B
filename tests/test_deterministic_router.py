from __future__ import annotations

import unittest

from src.deterministic_router import build_query, classify_route
from src.schemas import InputMessage


def route(*contents: str) -> str:
    return classify_route(
        [InputMessage(role="user", content=content) for content in contents]
    )


class ClassifyRouteTest(unittest.TestCase):
    def test_general_question_stays_direct(self) -> None:
        self.assertEqual(route("머리가 아픈데 집에서 뭘 하면 좋을까요?"), "direct")

    def test_empty_history_stays_direct(self) -> None:
        self.assertEqual(classify_route([]), "direct")

    def test_drug_dose_question_routes_to_drug_dose(self) -> None:
        self.assertEqual(
            route("이 약의 허가 용량과 금기를 확인해 주세요"), "drug_dose"
        )

    def test_law_question_routes_to_policy_legal(self) -> None:
        self.assertEqual(
            route("의료법 조문에 명시된 의무가 궁금해요"), "policy_legal"
        )

    def test_reimbursement_question_routes_to_policy_legal(self) -> None:
        self.assertEqual(
            route("이 약은 건강보험 급여 기준을 충족하나요?"), "policy_legal"
        )

    def test_guideline_question_routes_to_medical_evidence(self) -> None:
        self.assertEqual(
            route("최신 고혈압 진료지침의 목표 혈압을 알려주세요"),
            "medical_evidence",
        )

    def test_prior_turn_entity_still_counts(self) -> None:
        self.assertEqual(
            route("이 약 이름은 메트포르민이에요", "부작용이 궁금해요"),
            "drug_dose",
        )


class BuildQueryTest(unittest.TestCase):
    def test_empty_history_returns_empty_string(self) -> None:
        self.assertEqual(build_query([]), "")

    def test_single_turn_returns_that_turn(self) -> None:
        history = [InputMessage(role="user", content="질문입니다")]
        self.assertEqual(build_query(history), "질문입니다")

    def test_self_contained_followup_uses_latest_turn_only(self) -> None:
        history = [
            InputMessage(role="user", content="이전 질문"),
            InputMessage(
                role="user",
                content="65세 환자의 신기능 저하 시 용량 조정이 궁금합니다",
            ),
        ]
        self.assertEqual(
            build_query(history),
            "65세 환자의 신기능 저하 시 용량 조정이 궁금합니다",
        )

    def test_short_followup_prepends_previous_turn(self) -> None:
        history = [
            InputMessage(role="user", content="메트포르민 부작용이 궁금해요"),
            InputMessage(role="user", content="용량은요?"),
        ]
        self.assertEqual(
            build_query(history), "메트포르민 부작용이 궁금해요 용량은요?"
        )


if __name__ == "__main__":
    unittest.main()
