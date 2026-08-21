from __future__ import annotations

import os
from dataclasses import dataclass

from src.errors import ConfigurationError


# B009 bounded L2 attempt timeout. These values define model behavior and must
# change in source (with a new B version), never through deployment environment.
UPSTREAM_TIMEOUT_SECONDS = 30.0
REQUEST_TIMEOUT_SECONDS = 120.0
RETRIEVAL_TIMEOUT_SECONDS = 40.0
FINAL_GENERATION_RESERVE_SECONDS = 50.0
MCP_TOOL_TIMEOUT_SECONDS = 20.0
MCP_TERMINATE_ON_CLOSE = False
UPSTREAM_RETRIES = 1
UPSTREAM_CONCURRENCY = 5
UPSTREAM_PRIORITY_SLOTS = 1
RETRY_BASE_SECONDS = 0.5
RETRY_MAX_SECONDS = 8.0
MAX_GENERATION_ROUNDS = 3
MAX_RETRIEVALS_PER_ANSWER = 1
MAX_RETRIEVAL_MODEL_ROUNDS = 5
MAX_RETRIEVAL_MCP_CALLS = 3
MAX_MCP_RESULT_CHARS = 8_000
MAX_RETRIEVAL_CONTEXT_CHARS = 20_000
MAX_EVIDENCE_CHARS = 16_000
MAX_SELECTED_EVIDENCE = 2
CITATION_REPAIR_MIN_SECONDS = 15.0
RETRIEVAL_ENABLED = True
RETRIEVAL_GATE_ENABLED = True


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
    citation_repair_min_seconds: float
    retrieval_enabled: bool
    retrieval_gate_enabled: bool

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
            citation_repair_min_seconds=CITATION_REPAIR_MIN_SECONDS,
            retrieval_enabled=RETRIEVAL_ENABLED,
            retrieval_gate_enabled=RETRIEVAL_GATE_ENABLED,
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
