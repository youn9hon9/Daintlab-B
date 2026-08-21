from __future__ import annotations

import unittest

from src.schemas import ResolvedEvidence
from src.validation import remove_unknown_citations, validate_answer


def _evidence(citation: str, cite_uid: str) -> ResolvedEvidence:
    return ResolvedEvidence(
        citation=citation,
        cite_uid=cite_uid,
        relevance_score=1.0,
        source_tool="fake_search",
        payload={},
    )


class ValidationTest(unittest.TestCase):
    def test_unknown_citation_flagged(self) -> None:
        evidence = [_evidence("[1]", "cite-1")]

        result = validate_answer("근거 [1][2] 기반 답변", evidence, "sufficient")

        self.assertEqual(result.unknown_citations, ["[2]"])
        self.assertTrue(result.has_gap)

    def test_missing_citation_despite_sufficient_evidence(self) -> None:
        evidence = [_evidence("[1]", "cite-1")]

        result = validate_answer("근거 없이 작성한 답변", evidence, "sufficient")

        self.assertTrue(result.missing_citation_despite_evidence)
        self.assertTrue(result.has_gap)

    def test_no_evidence_with_no_citations_is_clean(self) -> None:
        result = validate_answer("일반적인 답변", [], "no_evidence")

        self.assertFalse(result.has_gap)

    def test_matching_citation_is_clean(self) -> None:
        evidence = [_evidence("[1]", "cite-1")]

        result = validate_answer("근거 기반 답변 [1]", evidence, "sufficient")

        self.assertFalse(result.has_gap)

    def test_unknown_citation_removal(self) -> None:
        result = validate_answer("근거 [9]", [], "no_evidence")
        self.assertEqual(remove_unknown_citations("근거 [9]", result), "근거")


if __name__ == "__main__":
    unittest.main()
