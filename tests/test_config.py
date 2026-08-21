from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src.config import (
    FINAL_GENERATION_RESERVE_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    Settings,
)


class SettingsTest(unittest.TestCase):
    def test_balanced_deadline_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.upstream_timeout_seconds, 50.0)
        self.assertEqual(settings.request_timeout_seconds, 120.0)
        self.assertEqual(settings.retrieval_timeout_seconds, 40.0)
        self.assertEqual(settings.final_generation_reserve_seconds, 50.0)
        self.assertEqual(settings.mcp_tool_timeout_seconds, 18.0)
        self.assertFalse(settings.mcp_terminate_on_close)
        self.assertEqual(settings.upstream_retries, 1)
        self.assertEqual(settings.upstream_concurrency, 4)
        self.assertEqual(settings.upstream_priority_slots, 1)
        self.assertEqual(settings.max_retrievals_per_answer, 1)
        self.assertEqual(settings.max_retrieval_model_rounds, 4)
        self.assertEqual(settings.max_retrieval_mcp_calls, 2)
        self.assertEqual(settings.max_mcp_result_chars, 8_000)
        self.assertEqual(settings.max_retrieval_context_chars, 12_000)
        self.assertEqual(settings.max_evidence_chars, 10_000)
        self.assertEqual(settings.max_selected_evidence, 2)

    def test_runtime_budget_environment_is_ignored(self) -> None:
        with patch.dict(
            os.environ,
            {
                "REQUEST_TIMEOUT_SECONDS": "1",
                "RETRIEVAL_TIMEOUT_SECONDS": "1",
                "UPSTREAM_CONCURRENCY": "1",
                "MAX_RETRIEVAL_MCP_CALLS": "99",
                "MAX_SELECTED_EVIDENCE": "99",
                "MCP_TERMINATE_ON_CLOSE": "true",
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.request_timeout_seconds, 120.0)
        self.assertEqual(settings.retrieval_timeout_seconds, 40.0)
        self.assertEqual(settings.upstream_concurrency, 4)
        self.assertEqual(settings.max_retrieval_mcp_calls, 2)
        self.assertEqual(settings.max_selected_evidence, 2)
        self.assertFalse(settings.mcp_terminate_on_close)

    def test_endpoint_and_identity_fields_still_read_environment(self) -> None:
        with patch.dict(
            os.environ,
            {
                "LUNIT_FM_API_KEY": "test-key",
                "LUNIT_FM_API_URL": "https://model.example.test/",
                "LUNIT_FM_MODEL": "Lunit/L2-custom",
                "LUNIT_MCP_URL": "https://mcp.example.test/mcp",
                "DRIVER_MODEL_ID": "custom-driver",
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.lunit_fm_api_key, "test-key")
        self.assertEqual(settings.lunit_fm_api_url, "https://model.example.test")
        self.assertEqual(settings.lunit_fm_model, "Lunit/L2-custom")
        self.assertEqual(settings.lunit_mcp_url, "https://mcp.example.test/mcp")
        self.assertEqual(settings.driver_model_id, "custom-driver")

    def test_final_generation_reserve_fits_request_deadline_constant(self) -> None:
        self.assertLess(
            FINAL_GENERATION_RESERVE_SECONDS, REQUEST_TIMEOUT_SECONDS
        )


if __name__ == "__main__":
    unittest.main()
