from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src.config import Settings


class SettingsTest(unittest.TestCase):
    def test_balanced_deadline_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.upstream_timeout_seconds, 50.0)
        self.assertEqual(settings.request_timeout_seconds, 120.0)
        self.assertEqual(settings.retrieval_timeout_seconds, 40.0)
        self.assertEqual(settings.final_generation_reserve_seconds, 50.0)
        self.assertEqual(settings.mcp_tool_timeout_seconds, 20.0)
        self.assertFalse(settings.mcp_terminate_on_close)
        self.assertEqual(settings.upstream_retries, 1)
        self.assertEqual(settings.upstream_concurrency, 5)
        self.assertEqual(settings.upstream_priority_slots, 1)
        self.assertEqual(settings.max_retrievals_per_answer, 1)
        self.assertEqual(settings.max_retrieval_model_rounds, 5)
        self.assertEqual(settings.max_retrieval_mcp_calls, 3)
        self.assertEqual(settings.max_mcp_result_chars, 8_000)
        self.assertEqual(settings.max_retrieval_context_chars, 20_000)
        self.assertEqual(settings.max_evidence_chars, 16_000)
        self.assertEqual(settings.max_selected_evidence, 2)
        self.assertFalse(settings.retrieval_enabled)

    def test_runtime_budget_environment_is_ignored(self) -> None:
        with patch.dict(
            os.environ,
            {
                "REQUEST_TIMEOUT_SECONDS": "1",
                "MAX_RETRIEVAL_MCP_CALLS": "99",
                "MCP_TERMINATE_ON_CLOSE": "true",
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.request_timeout_seconds, 120.0)
        self.assertEqual(settings.max_retrieval_mcp_calls, 3)
        self.assertFalse(settings.mcp_terminate_on_close)


if __name__ == "__main__":
    unittest.main()
