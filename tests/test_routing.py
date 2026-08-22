from __future__ import annotations

import unittest

from src.routing import should_offer_retrieval
from src.schemas import InputMessage


def route(*contents: str) -> bool:
    return should_offer_retrieval(
        [InputMessage(role="user", content=content) for content in contents]
    )


class RetrievalRoutingTest(unittest.TestCase):
    def test_general_symptom_question_stays_direct(self) -> None:
        self.assertFalse(route("머리가 아픈데 집에서 뭘 하면 좋을까요?"))

    def test_lifestyle_question_stays_direct(self) -> None:
        self.assertFalse(route("잠을 잘 자려면 어떻게 해야 하나요?"))

    def test_guideline_question_enables_retrieval(self) -> None:
        self.assertTrue(route("최신 고혈압 가이드라인 목표를 알려주세요"))

    def test_drug_dose_question_enables_retrieval(self) -> None:
        self.assertTrue(route("이 약의 허가 용량과 금기를 확인해 주세요"))

    def test_prior_turn_can_preserve_retrieval_intent(self) -> None:
        self.assertTrue(route("보험 급여 기준이 궁금해요", "한국 기준으로요"))


if __name__ == "__main__":
    unittest.main()
