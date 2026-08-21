"""Minimal asynchronous client for the official Lunit L2 chat API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import httpx


DEFAULT_API_URL = "https://model.hackathon.lunit.io"
DEFAULT_MODEL = "Lunit/L2-preview"


class L2ConfigurationError(RuntimeError):
    """Raised when required L2 configuration is unavailable."""


class L2UpstreamError(RuntimeError):
    """Raised when L2 cannot return a valid chat completion."""


@dataclass(frozen=True)
class L2Settings:
    api_url: str
    api_key: str
    model: str

    @classmethod
    def from_env(cls) -> "L2Settings":
        api_url = os.getenv("LUNIT_FM_API_URL", DEFAULT_API_URL).rstrip("/")
        api_key = os.getenv("LUNIT_FM_API_KEY", "")
        model = os.getenv("LUNIT_FM_MODEL", DEFAULT_MODEL)
        if not api_key:
            raise L2ConfigurationError("LUNIT_FM_API_KEY is required")
        if not api_url:
            raise L2ConfigurationError("LUNIT_FM_API_URL is required")
        if not model:
            raise L2ConfigurationError("LUNIT_FM_MODEL is required")
        return cls(api_url=api_url, api_key=api_key, model=model)


class L2Client:
    """Forward complete message histories to L2 without altering them."""

    def __init__(
        self,
        settings: L2Settings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings or L2Settings.from_env()
        self._transport = transport

    async def create_chat_completion(
        self, messages: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        payload = {
            "model": self.settings.model,
            "messages": [dict(message) for message in messages],
        }
        headers = {"Authorization": f"Bearer {self.settings.api_key}"}
        timeout = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    f"{self.settings.api_url}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
        except httpx.TimeoutException as exc:
            raise L2UpstreamError("L2 request timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise L2UpstreamError(
                f"L2 returned HTTP {exc.response.status_code}"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise L2UpstreamError("L2 request failed") from exc

        if not isinstance(result, dict) or not isinstance(result.get("choices"), list):
            raise L2UpstreamError("L2 returned an invalid chat completion")
        return result
