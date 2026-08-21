from __future__ import annotations

import unittest

from src.schemas import CompiledEvidenceItem
from src.validation import (
    assess_citation_grounding,
    remove_unknown_citations,
    validate_answer,
)


def _evidence(
    citation: str, cite_uid: str, excerpt: str = ""
) -> CompiledEvidenceItem:
    return CompiledEvidenceItem(
        citation=citation,
        cite_uid=cite_uid,
        source_tool="fake_search",
        excerpt=excerpt,
    )


class ValidationTest(unittest.TestCase):
    def test_unknown_citation_flagged(self) -> None:
        evidence = [_evidence("[1]", "cite-1")]

        result = validate_answer("근거 [1][2] 기반 답변", evidence)

        self.assertEqual(result.unknown_citations, ["[2]"])
        self.assertTrue(result.has_gap)

    def test_missing_citation_despite_sufficient_evidence(self) -> None:
        evidence = [_evidence("[1]", "cite-1")]

        result = validate_answer("근거 없이 작성한 답변", evidence)

        self.assertTrue(result.missing_citation_despite_evidence)
        self.assertTrue(result.has_gap)

    def test_no_evidence_with_no_citations_is_clean(self) -> None:
        result = validate_answer("일반적인 답변", [])

        self.assertFalse(result.has_gap)

    def test_matching_citation_is_clean(self) -> None:
        evidence = [_evidence("[1]", "cite-1")]

        result = validate_answer("근거 기반 답변 [1]", evidence)

        self.assertFalse(result.has_gap)

    def test_unknown_citation_removal(self) -> None:
        result = validate_answer("근거 [9]", [])
        self.assertEqual(remove_unknown_citations("근거 [9]", result), "근거")

    def test_grounding_check_flags_claim_unrelated_to_evidence(self) -> None:
        evidence = [
            _evidence(
                "[1]",
                "cite-1",
                excerpt="Metformin is first-line therapy for type 2 diabetes.",
            )
        ]

        checks = assess_citation_grounding(
            "The stock market rallied sharply today [1].", evidence
        )

        self.assertEqual(len(checks), 1)
        self.assertTrue(checks[0].low_grounding)

    def test_grounding_check_passes_claim_restating_evidence(self) -> None:
        evidence = [
            _evidence(
                "[1]",
                "cite-1",
                excerpt="Metformin is recommended as first-line therapy for type 2 diabetes.",
            )
        ]

        checks = assess_citation_grounding(
            "Metformin is recommended as first-line therapy for type 2 diabetes [1].",
            evidence,
        )

        self.assertEqual(len(checks), 1)
        self.assertFalse(checks[0].low_grounding)
        self.assertGreater(checks[0].overlap_ratio, 0.8)

    def test_grounding_check_returns_empty_without_evidence(self) -> None:
        checks = assess_citation_grounding("일반적인 답변 [1]", [])
        self.assertEqual(checks, [])

    def test_grounding_check_skips_citation_not_in_evidence(self) -> None:
        evidence = [_evidence("[1]", "cite-1", excerpt="some text")]

        checks = assess_citation_grounding("근거 없는 문장 [2].", evidence)

        self.assertEqual(checks, [])


if __name__ == "__main__":
    unittest.main()
