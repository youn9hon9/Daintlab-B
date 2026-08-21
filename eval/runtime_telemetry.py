"""Aggregate candidate stdout runtime events into a safe result summary."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


KNOWN_EVENTS = (
    "l2_input",
    "l2_attempt_complete",
    "l2_attempt_failed",
    "generation_complete",
    "generation_timed_out",
    "retrieval_complete",
    "retrieval_timed_out",
    "retrieval_skipped",
    "mcp_tool_complete",
    "mcp_tool_failed",
    "request_complete",
    "request_timed_out",
    "request_failed",
    "citation_repair_timed_out",
    "citation_repair_skipped",
)
REQUIRED_PHASES = {"initial", "retrieval", "final"}
EVENT_PATTERN = re.compile(r"\b(" + "|".join(KNOWN_EVENTS) + r")\b(.*)$")
FIELD_PATTERN = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)=([^\s]+)")
SAFE_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")


def _number(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _stats(values: list[float]) -> dict[str, float | int] | None:
    if not values:
        return None
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
        "max": max(values),
    }


def _safe_counter(values: list[str]) -> dict[str, int]:
    return dict(
        sorted(Counter(value for value in values if SAFE_VALUE_PATTERN.match(value)).items())
    )


def parse_candidate_log(text: str, expected_cases: int) -> dict[str, Any]:
    events: list[tuple[str, dict[str, str]]] = []
    for line in text.splitlines():
        match = EVENT_PATTERN.search(line)
        if match is None:
            continue
        fields = dict(FIELD_PATTERN.findall(match.group(2)))
        events.append((match.group(1), fields))

    phase_latencies: dict[str, list[float]] = defaultdict(list)
    phase_queue_waits: dict[str, list[float]] = defaultdict(list)
    phase_inputs: dict[str, list[float]] = defaultdict(list)
    phase_attempts: Counter[str] = Counter()
    phase_failures: Counter[str] = Counter()
    routes: list[str] = []
    retrieval_statuses: list[str] = []
    retrieval_latencies: list[float] = []
    request_latencies: list[float] = []
    request_terminal_events = 0
    mcp_successes = 0
    mcp_failures = 0
    counters: Counter[str] = Counter()

    for event, fields in events:
        counters[event] += 1
        phase = fields.get("phase", "unknown")
        if not SAFE_VALUE_PATTERN.match(phase):
            phase = "unknown"
        if event == "l2_input":
            value = _number(fields.get("message_chars"))
            if value is not None:
                phase_inputs[phase].append(value)
        elif event in {"l2_attempt_complete", "l2_attempt_failed"}:
            phase_attempts[phase] += 1
            if event == "l2_attempt_failed":
                phase_failures[phase] += 1
            latency = _number(fields.get("attempt_latency_ms"))
            queue_wait = _number(fields.get("queue_wait_ms"))
            if latency is not None:
                phase_latencies[phase].append(latency)
            if queue_wait is not None:
                phase_queue_waits[phase].append(queue_wait)
        elif event == "generation_complete":
            route = fields.get("route", "unknown")
            routes.append(route if SAFE_VALUE_PATTERN.match(route) else "unknown")
        elif event == "retrieval_complete":
            status = fields.get("status", "unknown")
            retrieval_statuses.append(
                status if SAFE_VALUE_PATTERN.match(status) else "unknown"
            )
            latency = _number(fields.get("latency_ms"))
            if latency is not None:
                retrieval_latencies.append(latency)
        elif event == "mcp_tool_complete":
            mcp_successes += 1
        elif event == "mcp_tool_failed":
            mcp_failures += 1
        elif event == "request_complete":
            request_terminal_events += 1
            latency = _number(fields.get("latency_ms"))
            if latency is not None:
                request_latencies.append(latency)
        elif event in {"request_timed_out", "request_failed"}:
            request_terminal_events += 1

    phases = sorted(set(phase_attempts) | set(phase_inputs))
    warnings: list[str] = []
    available = bool(events)
    route_coverage = len(routes) / expected_cases if expected_cases else 0.0
    request_coverage = (
        request_terminal_events / expected_cases if expected_cases else 0.0
    )
    observed_phases = set(phase_attempts)
    missing_phases = sorted(REQUIRED_PHASES - observed_phases)
    phase_metrics_available = not missing_phases
    if not available:
        warnings.append("candidate emitted no recognized runtime events")
    if route_coverage < 1.0:
        warnings.append("route telemetry does not cover every evaluation case")
    if request_coverage < 1.0:
        warnings.append("request terminal telemetry does not cover every evaluation case")
    if not phase_metrics_available:
        warnings.append(
            "L2 phase telemetry is missing: " + ", ".join(missing_phases)
        )
    if mcp_successes == 0 and counters["retrieval_complete"] > 0:
        warnings.append("successful MCP call count is unavailable in candidate logs")

    return {
        "schema_version": 1,
        "source": "candidate_stdout",
        "available": available,
        "telemetry_complete": (
            available
            and phase_metrics_available
            and route_coverage >= 1.0
            and request_coverage >= 1.0
        ),
        "warnings": warnings,
        "recognized_events": len(events),
        "request_coverage": request_coverage,
        "route_coverage": route_coverage,
        "missing_l2_phases": missing_phases,
        "routes": _safe_counter(routes),
        "requests": {
            "terminal": request_terminal_events,
            "complete": counters["request_complete"],
            "failed": counters["request_failed"],
            "timed_out": counters["request_timed_out"],
            "latency_ms": _stats(request_latencies),
        },
        "l2_phases": {
            phase: {
                "attempts": phase_attempts[phase],
                "failed_attempts": phase_failures[phase],
                "attempt_latency_ms": _stats(phase_latencies[phase]),
                "queue_wait_ms": _stats(phase_queue_waits[phase]),
                "input_chars": _stats(phase_inputs[phase]),
            }
            for phase in phases
        },
        "retrieval": {
            "complete": counters["retrieval_complete"],
            "timed_out": counters["retrieval_timed_out"],
            "skipped": counters["retrieval_skipped"],
            "statuses": _safe_counter(retrieval_statuses),
            "latency_ms": _stats(retrieval_latencies),
        },
        "mcp": {
            "successful_calls_observed": mcp_successes,
            "failed_calls_observed": mcp_failures,
            "complete_event_supported": mcp_successes > 0,
        },
        "generation_timeouts": counters["generation_timed_out"],
        "citation_repair_timeouts": counters["citation_repair_timed_out"],
    }


def merge_telemetry(result: dict[str, Any], telemetry: dict[str, Any]) -> None:
    result["runtime_telemetry"] = telemetry
    summary = result.setdefault("summary", {})
    warnings = list(summary.get("promotion_warnings", []))
    if not telemetry["telemetry_complete"]:
        warnings.append("runtime telemetry is incomplete")
    summary["promotion_warnings"] = warnings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = json.loads(args.result.read_text(encoding="utf-8"))
    expected_cases = len(result.get("records", []))
    log_text = args.log.read_text(encoding="utf-8", errors="replace")
    telemetry = parse_candidate_log(log_text, expected_cases)
    merge_telemetry(result, telemetry)
    args.result.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    status = "complete" if telemetry["telemetry_complete"] else "partial"
    print(f"runtime telemetry: {status}", flush=True)


if __name__ == "__main__":
    main()
