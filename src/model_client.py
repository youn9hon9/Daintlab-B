from __future__ import annotations

import asyncio
from typing import Any

import httpx2

from src.config import Settings
from src.errors import UpstreamError, UpstreamProtocolError


_RETRYABLE_STATUS_CODES = {429, 502, 503, 504}


class LunitModelClient:
    def __init__(
        self,
        settings: Settings,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._owns_client = http_client is None
        self._client = http_client or httpx2.AsyncClient(
            timeout=httpx2.Timeout(settings.upstream_timeout_seconds),
            follow_redirects=True,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        api_key = self.settings.require_api_key()
        payload: dict[str, Any] = {
            "model": self.settings.lunit_fm_model,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice

        endpoint = f"{self.settings.lunit_fm_api_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(self.settings.upstream_retries + 1):
            try:
                response = await self._client.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                )
            except (httpx2.TimeoutException, httpx2.TransportError) as exc:
                last_error = exc
                if attempt >= self.settings.upstream_retries:
                    break
                await asyncio.sleep(0.5 * (2**attempt))
                continue

            if response.status_code in _RETRYABLE_STATUS_CODES:
                last_error = UpstreamError(
                    f"Lunit FM returned HTTP {response.status_code}"
                )
                if attempt < self.settings.upstream_retries:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue

            if response.status_code >= 400:
                raise UpstreamError(
                    f"Lunit FM returned HTTP {response.status_code}"
                )

            try:
                data = response.json()
            except ValueError as exc:
                raise UpstreamProtocolError(
                    "Lunit FM returned invalid JSON"
                ) from exc
            return self._extract_message(data)

        raise UpstreamError("Lunit FM request failed after retries") from last_error

    @staticmethod
    def _extract_message(data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise UpstreamProtocolError("Lunit FM response must be an object")
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise UpstreamProtocolError("Lunit FM response has no choices")
        first = choices[0]
        if not isinstance(first, dict) or not isinstance(first.get("message"), dict):
            raise UpstreamProtocolError("Lunit FM response has no message")
        return dict(first["message"])

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

