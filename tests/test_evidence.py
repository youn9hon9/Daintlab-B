from __future__ import annotations

import unittest

from src.evidence import EvidenceRegistry
from src.schemas import CitationSelection


class EvidenceRegistryTest(unittest.TestCase):
    def test_unknown_uid_downgrades_to_no_evidence(self) -> None:
        registry = EvidenceRegistry(max_chars=1000)
        selection = CitationSelection.model_validate(
            {
                "status": "sufficient",
                "items": [
                    {"cite_uid": "cite-missing", "relevance_score": 0.9}
                ],
                "note": "",
            }
        )

        result = registry.resolve(selection)

        self.assertEqual(result.status, "no_evidence")
        self.assertEqual(result.evidence, [])
        self.assertIn("unverified", result.note)

    def test_text_json_citation_is_captured(self) -> None:
        registry = EvidenceRegistry(max_chars=1000)
        registry.capture(
            "fake_search",
            {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            '{"cite_uid":"cite-known","content":"evidence"}'
                        ),
                    }
                ]
            },
        )
        selection = CitationSelection.model_validate(
            {
                "status": "sufficient",
                "items": [
                    {"cite_uid": "cite-known", "relevance_score": 1.0}
                ],
            }
        )

        result = registry.resolve(selection)

        self.assertEqual(result.status, "sufficient")
        self.assertEqual(result.evidence[0].source_tool, "fake_search")

    def test_role_defaults_to_primary_and_propagates_when_set(self) -> None:
        registry = EvidenceRegistry(max_chars=10_000)
        registry.capture(
            "fake_search",
            {"cite_uid": "cite-primary", "content": "main finding"},
        )
        registry.capture(
            "other_search",
            {"cite_uid": "cite-caveat", "content": "exception"},
        )
        selection = CitationSelection.model_validate(
            {
                "status": "sufficient",
                "items": [
                    {"cite_uid": "cite-primary", "relevance_score": 1.0},
                    {
                        "cite_uid": "cite-caveat",
                        "relevance_score": 0.8,
                        "role": "caveat",
                    },
                ],
            }
        )

        result = registry.resolve(selection)

        self.assertEqual(result.evidence[0].role, "primary")
        self.assertEqual(result.evidence[1].role, "caveat")

    def test_selected_evidence_is_limited_to_max_items(self) -> None:
        registry = EvidenceRegistry(max_chars=10_000, max_items=2)
        for index in range(3):
            registry.capture(
                "fake_search",
                {
                    "cite_uid": f"cite-{index}",
                    "content": f"evidence {index}",
                },
            )
        selection = CitationSelection.model_validate(
            {
                "status": "sufficient",
                "items": [
                    {
                        "cite_uid": f"cite-{index}",
                        "relevance_score": 1.0 - index / 10,
                    }
                    for index in range(3)
                ],
            }
        )

        result = registry.resolve(selection)

        self.assertEqual(result.status, "partial")
        self.assertEqual(
            [item.cite_uid for item in result.evidence],
            ["cite-0", "cite-1"],
        )
        self.assertIn("Limited evidence to 2", result.note)


if __name__ == "__main__":
    unittest.main()
