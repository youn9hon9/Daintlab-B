from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src.config import Settings
from src.errors import ConfigurationError


class SettingsTest(unittest.TestCase):
    def test_lean_retrieval_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.upstream_timeout_seconds, 60.0)
        self.assertEqual(settings.upstream_concurrency, 2)
        self.assertEqual(settings.max_retrievals_per_answer, 1)
        self.assertEqual(settings.max_retrieval_model_rounds, 6)
        self.assertEqual(settings.max_retrieval_mcp_calls, 4)
        self.assertEqual(settings.max_mcp_result_chars, 10_000)
        self.assertEqual(settings.max_retrieval_context_chars, 32_000)
        self.assertEqual(settings.max_evidence_chars, 24_000)
        self.assertEqual(settings.max_selected_evidence, 3)

    def test_final_generation_reserve_must_fit_request_deadline(self) -> None:
        with patch.dict(
            os.environ,
            {
                "REQUEST_TIMEOUT_SECONDS": "10",
                "FINAL_GENERATION_RESERVE_SECONDS": "10",
            },
            clear=True,
        ):
            with self.assertRaises(ConfigurationError):
                Settings.from_env()


if __name__ == "__main__":
    unittest.main()
