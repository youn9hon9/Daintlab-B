from __future__ import annotations

import os
from dataclasses import dataclass

from src.errors import ConfigurationError


# F004 control budgets. These values define evaluated model behavior and must
# change in source (with a new F version), never through deployment environment.
#
# F003 changed upstream/request/final-reserve/mcp-tool timeouts AND
# concurrency together (all "D5's throughput cluster" at once) and got 11/32
# success (down from F002's 29/32) with 20x HTTP 502 + 1x 504. That result
# cannot tell us whether the 30s upstream timeout or the concurrency=6 change
# caused the collapse -- exactly the multi-variable confound this repo's own
# incidents (B001, F001) warn against, and D5's own local eval already showed
# the same 30s-upstream-timeout failure signature (11/16, 502s from
# ReadTimeout) even though its real Trial passed. F004 isolates concurrency
# as the only tested variable: timeouts revert to F002's values, and only
# UPSTREAM_CONCURRENCY changes, from F002's 2 toward D5's 6 in one smaller
# step (4), per both F002's and F003's own postmortem recommendations.
UPSTREAM_TIMEOUT_SECONDS = 50.0
REQUEST_TIMEOUT_SECONDS = 120.0
RETRIEVAL_TIMEOUT_SECONDS = 40.0
FINAL_GENERATION_RESERVE_SECONDS = 50.0
MCP_TOOL_TIMEOUT_SECONDS = 18.0
MCP_TERMINATE_ON_CLOSE = False
UPSTREAM_RETRIES = 1
UPSTREAM_CONCURRENCY = 4
UPSTREAM_PRIORITY_SLOTS = 1
RETRY_BASE_SECONDS = 0.5
RETRY_MAX_SECONDS = 8.0
MAX_GENERATION_ROUNDS = 3
MAX_RETRIEVALS_PER_ANSWER = 1
# The retrieval-shape cluster below is deliberately left at F001/F002's
# tighter, locally-validated values instead of D5's larger defaults (5
# rounds, 3 MCP calls, 20,000/16,000 char budgets). D5's real Trial success
# says nothing about whether its retrieval-shape values were necessary; no
# postmortem (Y2 timeout incident, F001, F002) has implicated these fields,
# so copying them here would be an unjustified second variable alongside the
# throughput realignment above.
MAX_RETRIEVAL_MODEL_ROUNDS = 4
MAX_RETRIEVAL_MCP_CALLS = 2
MAX_MCP_RESULT_CHARS = 8_000
MAX_RETRIEVAL_CONTEXT_CHARS = 12_000
MAX_EVIDENCE_CHARS = 10_000
MAX_SELECTED_EVIDENCE = 2


@dataclass(frozen=True, slots=True)
class Settings:
    driver_model_id: str
    lunit_fm_api_url: str
    lunit_fm_api_key: str
    lunit_fm_model: str
    lunit_mcp_url: str
    upstream_timeout_seconds: float
    request_timeout_seconds: float
    retrieval_timeout_seconds: float
    final_generation_reserve_seconds: float
    mcp_tool_timeout_seconds: float
    mcp_terminate_on_close: bool
    upstream_retries: int
    upstream_concurrency: int
    upstream_priority_slots: int
    retry_base_seconds: float
    retry_max_seconds: float
    max_generation_rounds: int
    max_retrievals_per_answer: int
    max_retrieval_model_rounds: int
    max_retrieval_mcp_calls: int
    max_mcp_result_chars: int
    max_retrieval_context_chars: int
    max_evidence_chars: int
    max_selected_evidence: int

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            driver_model_id=os.getenv(
                "DRIVER_MODEL_ID", "lunit-hackathon-driver"
            ).strip(),
            # F011: default points at the failover L2 endpoint
            # (http://61.107.202.7:9412) since the official endpoint's L2
            # instance was producing 429s, ~50s ReadTimeouts, and large
            # latency variance. LUNIT_FM_API_URL still overrides this at
            # deployment time -- only the default changed.
            lunit_fm_api_url=os.getenv(
                "LUNIT_FM_API_URL", "http://61.107.202.7:9412"
            ).rstrip("/"),
            lunit_fm_api_key=os.getenv("LUNIT_FM_API_KEY", "").strip(),
            lunit_fm_model=os.getenv(
                "LUNIT_FM_MODEL", "Lunit/L2-preview"
            ).strip(),
            lunit_mcp_url=os.getenv(
                "LUNIT_MCP_URL", "https://mcp.hackathon.lunit.io/mcp"
            ).strip(),
            upstream_timeout_seconds=UPSTREAM_TIMEOUT_SECONDS,
            request_timeout_seconds=REQUEST_TIMEOUT_SECONDS,
            retrieval_timeout_seconds=RETRIEVAL_TIMEOUT_SECONDS,
            final_generation_reserve_seconds=FINAL_GENERATION_RESERVE_SECONDS,
            mcp_tool_timeout_seconds=MCP_TOOL_TIMEOUT_SECONDS,
            mcp_terminate_on_close=MCP_TERMINATE_ON_CLOSE,
            upstream_retries=UPSTREAM_RETRIES,
            upstream_concurrency=UPSTREAM_CONCURRENCY,
            upstream_priority_slots=UPSTREAM_PRIORITY_SLOTS,
            retry_base_seconds=RETRY_BASE_SECONDS,
            retry_max_seconds=RETRY_MAX_SECONDS,
            max_generation_rounds=MAX_GENERATION_ROUNDS,
            max_retrievals_per_answer=MAX_RETRIEVALS_PER_ANSWER,
            max_retrieval_model_rounds=MAX_RETRIEVAL_MODEL_ROUNDS,
            max_retrieval_mcp_calls=MAX_RETRIEVAL_MCP_CALLS,
            max_mcp_result_chars=MAX_MCP_RESULT_CHARS,
            max_retrieval_context_chars=MAX_RETRIEVAL_CONTEXT_CHARS,
            max_evidence_chars=MAX_EVIDENCE_CHARS,
            max_selected_evidence=MAX_SELECTED_EVIDENCE,
        )
        if (
            settings.final_generation_reserve_seconds
            >= settings.request_timeout_seconds
        ):
            raise ConfigurationError(
                "FINAL_GENERATION_RESERVE_SECONDS must be less than "
                "REQUEST_TIMEOUT_SECONDS"
            )
        return settings

    def require_api_key(self) -> str:
        if not self.lunit_fm_api_key:
            raise ConfigurationError("LUNIT_FM_API_KEY is not configured")
        return self.lunit_fm_api_key
