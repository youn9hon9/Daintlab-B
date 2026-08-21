from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src.config import Settings
from src.errors import ConfigurationError


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
        self.assertEqual(settings.upstream_concurrency, 2)
        self.assertEqual(settings.upstream_priority_slots, 1)
        self.assertEqual(settings.max_retrievals_per_answer, 1)
        self.assertEqual(settings.max_retrieval_model_rounds, 4)
        self.assertEqual(settings.max_retrieval_mcp_calls, 2)
        self.assertEqual(settings.max_mcp_result_chars, 8_000)
        self.assertEqual(settings.max_retrieval_context_chars, 12_000)
        self.assertEqual(settings.max_evidence_chars, 10_000)
        self.assertEqual(settings.max_selected_evidence, 2)

    def test_mcp_terminate_on_close_accepts_strict_boolean_values(self) -> None:
        accepted = {
            "true": True,
            "TRUE": True,
            "1": True,
            "yes": True,
            " false ": False,
            "FALSE": False,
            "0": False,
            "no": False,
        }
        for raw, expected in accepted.items():
            with self.subTest(raw=raw):
                with patch.dict(
                    os.environ,
                    {"MCP_TERMINATE_ON_CLOSE": raw},
                    clear=True,
                ):
                    settings = Settings.from_env()
                self.assertIs(settings.mcp_terminate_on_close, expected)

    def test_mcp_terminate_on_close_rejects_other_values(self) -> None:
        for raw in ("", "on", "off", "2", "maybe"):
            with self.subTest(raw=raw):
                with patch.dict(
                    os.environ,
                    {"MCP_TERMINATE_ON_CLOSE": raw},
                    clear=True,
                ):
                    with self.assertRaises(ConfigurationError):
                        Settings.from_env()

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
