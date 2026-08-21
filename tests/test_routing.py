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

    def test_empathy_request_stays_direct(self) -> None:
        self.assertFalse(route("진단을 기다리는 동안 너무 불안해요"))

    def test_guideline_question_enables_retrieval(self) -> None:
        self.assertTrue(route("최신 고혈압 가이드라인 목표를 알려주세요"))

    def test_approval_and_dose_question_enables_retrieval(self) -> None:
        self.assertTrue(route("이 약의 허가 용량과 금기를 확인해 주세요"))

    def test_prior_turn_preserves_reimbursement_intent(self) -> None:
        self.assertTrue(route("보험 적용 기준이 궁금해요", "한국 기준으로요"))

    def test_assistant_text_does_not_enable_retrieval(self) -> None:
        history = [
            InputMessage(role="assistant", content="최신 가이드라인"),
            InputMessage(role="user", content="그냥 설명해 주세요"),
        ]
        self.assertFalse(should_offer_retrieval(history))
