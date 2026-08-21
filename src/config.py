from __future__ import annotations

import os
from dataclasses import dataclass

from src.errors import ConfigurationError


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ConfigurationError(f"{name} must be at least {minimum}")
    return value


def _float_env(name: str, default: float, minimum: float = 0.1) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number") from exc
    if value < minimum:
        raise ConfigurationError(f"{name} must be at least {minimum}")
    return value


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ConfigurationError(
        f"{name} must be one of true, false, 1, 0, yes, or no"
    )


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
            upstream_timeout_seconds=_float_env(
                "UPSTREAM_TIMEOUT_SECONDS", 50.0
            ),
            request_timeout_seconds=_float_env(
                "REQUEST_TIMEOUT_SECONDS", 120.0
            ),
            retrieval_timeout_seconds=_float_env(
                "RETRIEVAL_TIMEOUT_SECONDS", 40.0
            ),
            final_generation_reserve_seconds=_float_env(
                "FINAL_GENERATION_RESERVE_SECONDS", 50.0
            ),
            mcp_tool_timeout_seconds=_float_env(
                "MCP_TOOL_TIMEOUT_SECONDS", 18.0
            ),
            mcp_terminate_on_close=_bool_env(
                "MCP_TERMINATE_ON_CLOSE", False
            ),
            upstream_retries=_int_env("UPSTREAM_RETRIES", 1, minimum=0),
            upstream_concurrency=_int_env("UPSTREAM_CONCURRENCY", 2),
            upstream_priority_slots=_int_env(
                "UPSTREAM_PRIORITY_SLOTS", 1, minimum=0
            ),
            retry_base_seconds=_float_env("RETRY_BASE_SECONDS", 0.5),
            retry_max_seconds=_float_env("RETRY_MAX_SECONDS", 8.0),
            max_generation_rounds=_int_env("MAX_GENERATION_ROUNDS", 3),
            max_retrievals_per_answer=_int_env(
                "MAX_RETRIEVALS_PER_ANSWER", 1
            ),
            max_retrieval_model_rounds=_int_env(
                "MAX_RETRIEVAL_MODEL_ROUNDS", 4
            ),
            max_retrieval_mcp_calls=_int_env(
                "MAX_RETRIEVAL_MCP_CALLS", 2
            ),
            max_mcp_result_chars=_int_env(
                "MAX_MCP_RESULT_CHARS", 8_000, minimum=1_024
            ),
            max_retrieval_context_chars=_int_env(
                "MAX_RETRIEVAL_CONTEXT_CHARS", 12_000, minimum=1_024
            ),
            max_evidence_chars=_int_env("MAX_EVIDENCE_CHARS", 10_000),
            max_selected_evidence=_int_env("MAX_SELECTED_EVIDENCE", 2),
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
