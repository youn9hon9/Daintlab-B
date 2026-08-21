from __future__ import annotations

import unittest

from src.retrieval_policy import should_offer_retrieval
from src.schemas import InputMessage


class RetrievalPolicyTest(unittest.TestCase):
    def test_general_symptom_question_uses_direct_path(self) -> None:
        history = [
            InputMessage(
                role="user",
                content=(
                    "What symptoms should I check for when I have a severe "
                    "headache?"
                ),
            )
        ]

        self.assertFalse(should_offer_retrieval(history))

    def test_explicit_guideline_request_allows_retrieval(self) -> None:
        history = [
            InputMessage(
                role="user",
                content="Cite the latest guideline for hypertension treatment.",
            )
        ]

        self.assertTrue(should_offer_retrieval(history))

    def test_latest_lab_result_does_not_trigger_retrieval(self) -> None:
        history = [
            InputMessage(
                role="user",
                content="My latest lab result shows a potassium level of 5.5.",
            )
        ]

        self.assertFalse(should_offer_retrieval(history))

    def test_source_as_cause_does_not_trigger_retrieval(self) -> None:
        history = [
            InputMessage(
                role="user",
                content="Could dehydration be the source of my headache?",
            )
        ]

        self.assertFalse(should_offer_retrieval(history))

    def test_explicit_reference_request_allows_retrieval(self) -> None:
        history = [
            InputMessage(
                role="user",
                content="Please include references for your recommendation.",
            )
        ]

        self.assertTrue(should_offer_retrieval(history))

    def test_approval_request_allows_retrieval(self) -> None:
        history = [
            InputMessage(
                role="user",
                content="What is the MFDS-approved indication for metformin?",
            )
        ]

        self.assertTrue(should_offer_retrieval(history))

    def test_prior_source_request_carries_into_follow_up(self) -> None:
        history = [
            InputMessage(
                role="user",
                content="Please use a source for the US recommendation.",
            ),
            InputMessage(role="assistant", content="Here is the US guidance."),
            InputMessage(role="user", content="What about Korea?"),
        ]

        self.assertTrue(should_offer_retrieval(history))


if __name__ == "__main__":
    unittest.main()
