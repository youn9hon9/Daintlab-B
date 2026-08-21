from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, patch

from src.model_client import LunitModelClient


_SUCCESS_BODY = {
    "choices": [
        {"message": {"role": "assistant", "content": "ok"}},
    ]
}


@dataclass
class FakeSettings:
    lunit_fm_api_url: str = "https://model.example.test"
    lunit_fm_api_key: str = "test-key"
    lunit_fm_model: str = "Lunit/L2-preview"
    upstream_timeout_seconds: float = 1.0
    upstream_retries: int = 1
    upstream_concurrency: int = 2
    retry_base_seconds: float = 0.5
    retry_max_seconds: float = 8.0

    def require_api_key(self) -> str:
        return self.lunit_fm_api_key


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        *,
        headers: dict[str, str] | None = None,
        body: Any = None,
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self._body = _SUCCESS_BODY if body is None else body

    def json(self) -> Any:
        return self._body


class SequenceHTTPClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls = 0

    async def post(self, *args: Any, **kwargs: Any) -> FakeResponse:
        self.calls += 1
        if not self.responses:
            raise AssertionError("Fake HTTP client has no response left")
        return self.responses.pop(0)


class BlockingHTTPClient:
    def __init__(self, expected_concurrency: int) -> None:
        self.expected_concurrency = expected_concurrency
        self.release = asyncio.Event()
        self.limit_reached = asyncio.Event()
        self.started = 0
        self.active = 0
        self.max_active = 0

    async def post(self, *args: Any, **kwargs: Any) -> FakeResponse:
        self.started += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        if self.active >= self.expected_concurrency:
            self.limit_reached.set()
        try:
            await self.release.wait()
            return FakeResponse(200)
        finally:
            self.active -= 1


class LunitModelClientTest(unittest.IsolatedAsyncioTestCase):
    async def test_retries_http_500_with_full_jitter(self) -> None:
        http_client = SequenceHTTPClient(
            [FakeResponse(500), FakeResponse(200)]
        )
        client = LunitModelClient(FakeSettings(), http_client=http_client)

        with (
            patch(
                "src.model_client.random.uniform", return_value=0.25
            ) as uniform,
            patch(
                "src.model_client.asyncio.sleep", new_callable=AsyncMock
            ) as sleep,
        ):
            result = await client.chat([{"role": "user", "content": "question"}])

        self.assertEqual(result["content"], "ok")
        self.assertEqual(http_client.calls, 2)
        uniform.assert_called_once_with(0.0, 0.5)
        sleep.assert_awaited_once_with(0.25)

    async def test_retries_http_429_using_retry_after(self) -> None:
        http_client = SequenceHTTPClient(
            [
                FakeResponse(429, headers={"Retry-After": "2.5"}),
                FakeResponse(200),
            ]
        )
        client = LunitModelClient(FakeSettings(), http_client=http_client)

        with (
            patch("src.model_client.random.uniform") as uniform,
            patch(
                "src.model_client.asyncio.sleep", new_callable=AsyncMock
            ) as sleep,
        ):
            result = await client.chat([{"role": "user", "content": "question"}])

        self.assertEqual(result["content"], "ok")
        self.assertEqual(http_client.calls, 2)
        uniform.assert_not_called()
        sleep.assert_awaited_once_with(2.5)

    async def test_limits_only_active_http_attempts(self) -> None:
        concurrency = 2
        http_client = BlockingHTTPClient(concurrency)
        client = LunitModelClient(
            FakeSettings(upstream_retries=0, upstream_concurrency=concurrency),
            http_client=http_client,
        )
        tasks = [
            asyncio.create_task(
                client.chat([{"role": "user", "content": f"question-{index}"}])
            )
            for index in range(5)
        ]

        try:
            await asyncio.wait_for(http_client.limit_reached.wait(), timeout=1.0)
            await asyncio.sleep(0)
            self.assertEqual(http_client.started, concurrency)
            self.assertEqual(http_client.max_active, concurrency)
        finally:
            http_client.release.set()

        results = await asyncio.gather(*tasks)
        self.assertEqual(len(results), 5)
        self.assertEqual(http_client.max_active, concurrency)


if __name__ == "__main__":
    unittest.main()
