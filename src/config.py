from __future__ import annotations

import os
from dataclasses import dataclass

from src.errors import ConfigurationError


# F010 control budgets. These values define evaluated model behavior and must
# change in source (with a new F version), never through deployment environment.
#
# F010 replaces the old Generation-L2 -> Retrieval-L2 -> final-L2 loop with a
# deterministic harness router + evidence compiler and exactly one L2 call
# per request (see src/deterministic_router.py, src/evidence_compiler.py).
# The old multi-round/multi-call settings (max_generation_rounds,
# max_retrievals_per_answer, max_retrieval_model_rounds,
# max_retrieval_mcp_calls, max_retrieval_context_chars, max_evidence_chars,
# max_selected_evidence, max_tokens_retrieval, retrieval_timeout_seconds) are
# removed along with src/retrieval.py -- there is no longer a second L2 call
# or a multi-round MCP loop for them to bound. UPSTREAM_RETRIES is 0 and
# UPSTREAM_PRIORITY_SLOTS is 0 because there is only one call type now: no
# "retry a ~50s call" and no "reserve a slot for the final phase" concept
# survives a one-L2-call-per-request design.
UPSTREAM_TIMEOUT_SECONDS = 50.0
REQUEST_TIMEOUT_SECONDS = 120.0
FINAL_GENERATION_RESERVE_SECONDS = 50.0
MCP_TOOL_TIMEOUT_SECONDS = 6.0
MCP_TERMINATE_ON_CLOSE = False
UPSTREAM_RETRIES = 0
UPSTREAM_CONCURRENCY = 4
UPSTREAM_PRIORITY_SLOTS = 0
RETRY_BASE_SECONDS = 0.5
RETRY_MAX_SECONDS = 8.0
MAX_MCP_RESULT_CHARS = 8_000
# Overall wall-clock budget for the whole evidence-compiler phase (route
# classification is instant; this covers the MCP call(s) only), enforced via
# asyncio.timeout in driver.py -- not a per-call timeout. MCP_TOOL_TIMEOUT_SECONDS
# bounds each individual call inside it.
EVIDENCE_COMPILER_TIMEOUT_SECONDS = 10.0
# Bound worst-case L2 output length for the single generation call.
MAX_TOKENS_ANSWER = 1024


@dataclass(frozen=True, slots=True)
class Settings:
    driver_model_id: str
    lunit_fm_api_url: str
    lunit_fm_api_key: str
    lunit_fm_model: str
    lunit_mcp_url: str
    upstream_timeout_seconds: float
    request_timeout_seconds: float
    final_generation_reserve_seconds: float
    mcp_tool_timeout_seconds: float
    mcp_terminate_on_close: bool
    upstream_retries: int
    upstream_concurrency: int
    upstream_priority_slots: int
    retry_base_seconds: float
    retry_max_seconds: float
    max_mcp_result_chars: int
    evidence_compiler_timeout_seconds: float
    max_tokens_answer: int

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            driver_model_id=os.getenv(
                "DRIVER_MODEL_ID", "lunit-hackathon-driver"
            ).strip(),
            lunit_fm_api_url=os.getenv(
                "LUNIT_FM_API_URL", "https://model.hackathon.lunit.io"
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
            final_generation_reserve_seconds=FINAL_GENERATION_RESERVE_SECONDS,
            mcp_tool_timeout_seconds=MCP_TOOL_TIMEOUT_SECONDS,
            mcp_terminate_on_close=MCP_TERMINATE_ON_CLOSE,
            upstream_retries=UPSTREAM_RETRIES,
            upstream_concurrency=UPSTREAM_CONCURRENCY,
            upstream_priority_slots=UPSTREAM_PRIORITY_SLOTS,
            retry_base_seconds=RETRY_BASE_SECONDS,
            retry_max_seconds=RETRY_MAX_SECONDS,
            max_mcp_result_chars=MAX_MCP_RESULT_CHARS,
            evidence_compiler_timeout_seconds=EVIDENCE_COMPILER_TIMEOUT_SECONDS,
            max_tokens_answer=MAX_TOKENS_ANSWER,
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
