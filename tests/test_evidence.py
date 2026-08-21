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


if __name__ == "__main__":
    unittest.main()

