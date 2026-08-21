import unittest

from eval.runtime_telemetry import merge_telemetry, parse_candidate_log


class RuntimeTelemetryTests(unittest.TestCase):
    def test_aggregates_routes_phases_queue_and_retrieval(self):
        log = """
INFO src.model_client l2_input phase=initial messages=2 message_chars=100 tools=1
INFO src.model_client l2_attempt_complete attempt=1 phase=initial queue_wait_ms=10 attempt_latency_ms=1000 status=200
INFO src.driver generation_complete route=direct generation_rounds=1 retrievals=0
INFO src.api request_complete id=one latency_ms=1200
INFO src.model_client l2_input phase=initial messages=2 message_chars=200 tools=1
INFO src.model_client l2_attempt_complete attempt=1 phase=initial queue_wait_ms=30 attempt_latency_ms=2000 status=200
INFO src.model_client l2_attempt_complete attempt=1 phase=retrieval queue_wait_ms=20 attempt_latency_ms=3000 status=200
INFO src.driver retrieval_complete status=complete latency_ms=3500 budget_seconds=40
INFO src.model_client l2_attempt_complete attempt=1 phase=final queue_wait_ms=40 attempt_latency_ms=4000 status=200
INFO src.driver generation_complete route=rag generation_rounds=2 retrievals=1
INFO src.api request_complete id=two latency_ms=10000
"""
        telemetry = parse_candidate_log(log, expected_cases=2)
        self.assertTrue(telemetry["telemetry_complete"])
        self.assertEqual(telemetry["routes"], {"direct": 1, "rag": 1})
        self.assertEqual(
            telemetry["l2_phases"]["initial"]["queue_wait_ms"]["p50"],
            20.0,
        )
        self.assertEqual(
            telemetry["l2_phases"]["final"]["attempt_latency_ms"]["max"],
            4000.0,
        )
        self.assertEqual(telemetry["retrieval"]["complete"], 1)

    def test_missing_events_adds_promotion_warning_without_rejecting_score(self):
        telemetry = parse_candidate_log("ordinary startup log", expected_cases=2)
        result = {"summary": {"promotion_eligible": True}}
        merge_telemetry(result, telemetry)
        self.assertFalse(telemetry["telemetry_complete"])
        self.assertTrue(result["summary"]["promotion_eligible"])
        self.assertEqual(
            result["summary"]["promotion_warnings"],
            ["runtime telemetry is incomplete"],
        )

    def test_failed_attempt_and_timeout_are_counted(self):
        log = """
WARNING l2_attempt_failed attempt=1 phase=final queue_wait_ms=50 attempt_latency_ms=120000 error_type=ReadTimeout
WARNING generation_timed_out phase=final budget_seconds=10
WARNING request_timed_out id=x
WARNING retrieval_timed_out budget_seconds=40
WARNING mcp_tool_failed tool=test error_type=MCPError
"""
        telemetry = parse_candidate_log(log, expected_cases=1)
        self.assertEqual(telemetry["l2_phases"]["final"]["failed_attempts"], 1)
        self.assertEqual(telemetry["generation_timeouts"], 1)
        self.assertEqual(telemetry["requests"]["timed_out"], 1)
        self.assertEqual(telemetry["retrieval"]["timed_out"], 1)
        self.assertEqual(telemetry["mcp"]["failed_calls_observed"], 1)
        self.assertEqual(telemetry["missing_l2_phases"], ["initial", "retrieval"])
        self.assertFalse(telemetry["telemetry_complete"])


if __name__ == "__main__":
    unittest.main()
