from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, patch

from src.errors import UpstreamError
from src.model_client import LunitModelClient, _PriorityLimiter


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
    upstream_priority_slots: int = 1
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


class OrderedHTTPClient:
    def __init__(self) -> None:
        self.order: list[str] = []
        self.first_started = asyncio.Event()
        self.release_first = asyncio.Event()

    async def post(self, *args: Any, **kwargs: Any) -> FakeResponse:
        label = kwargs["json"]["messages"][0]["content"]
        self.order.append(label)
        if len(self.order) == 1:
            self.first_started.set()
            await self.release_first.wait()
        return FakeResponse(200)


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
        client._transport_warmed = True
        self.assertEqual(client._upstream_limiter.normal_capacity, concurrency)
        self.assertEqual(client._upstream_limiter.capacity, concurrency + 1)
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

    async def test_serializes_only_cold_start_connection(self) -> None:
        http_client = OrderedHTTPClient()
        client = LunitModelClient(
            FakeSettings(upstream_retries=0, upstream_concurrency=2),
            http_client=http_client,
        )
        first = asyncio.create_task(
            client.chat([{"role": "user", "content": "first"}])
        )
        second = asyncio.create_task(
            client.chat([{"role": "user", "content": "second"}])
        )

        await asyncio.wait_for(http_client.first_started.wait(), timeout=1.0)
        await asyncio.sleep(0)
        self.assertEqual(http_client.order, ["first"])

        http_client.release_first.set()
        await asyncio.wait_for(asyncio.gather(first, second), timeout=1.0)

        self.assertEqual(http_client.order, ["first", "second"])
        self.assertTrue(client._transport_warmed)

    async def test_final_waiter_starts_before_queued_initial_waiter(self) -> None:
        http_client = OrderedHTTPClient()
        client = LunitModelClient(
            FakeSettings(upstream_retries=0, upstream_concurrency=1),
            http_client=http_client,
        )
        client._upstream_limiter = _PriorityLimiter(capacity=1)
        holder = asyncio.create_task(
            client.chat([{"role": "user", "content": "holder"}])
        )
        await asyncio.wait_for(http_client.first_started.wait(), timeout=1.0)

        normal = asyncio.create_task(
            client.chat([{"role": "user", "content": "normal"}])
        )
        await asyncio.sleep(0)
        final = asyncio.create_task(
            client.chat(
                [{"role": "user", "content": "final"}],
                phase="final",
            )
        )
        await asyncio.sleep(0)
        http_client.release_first.set()

        await asyncio.wait_for(
            asyncio.gather(holder, normal, final), timeout=1.0
        )
        self.assertEqual(
            http_client.order,
            ["holder", "final", "normal"],
        )

    async def test_retrieval_starts_before_queued_initial_waiter(self) -> None:
        http_client = OrderedHTTPClient()
        client = LunitModelClient(
            FakeSettings(upstream_retries=0, upstream_concurrency=1),
            http_client=http_client,
        )
        client._upstream_limiter = _PriorityLimiter(capacity=1)
        holder = asyncio.create_task(
            client.chat([{"role": "user", "content": "holder"}])
        )
        await asyncio.wait_for(http_client.first_started.wait(), timeout=1.0)

        initial = asyncio.create_task(
            client.chat([{"role": "user", "content": "initial"}])
        )
        await asyncio.sleep(0)
        retrieval = asyncio.create_task(
            client.chat(
                [{"role": "user", "content": "retrieval"}],
                phase="retrieval",
            )
        )
        await asyncio.sleep(0)
        http_client.release_first.set()

        await asyncio.wait_for(
            asyncio.gather(holder, initial, retrieval), timeout=1.0
        )
        self.assertEqual(
            http_client.order,
            ["holder", "retrieval", "initial"],
        )

    async def test_reserved_slot_starts_priority_while_normal_slots_are_full(
        self,
    ) -> None:
        limiter = _PriorityLimiter(capacity=2, reserved_priority_slots=1)
        await limiter.acquire(phase="initial")
        await limiter.acquire(phase="initial")

        blocked_normal = asyncio.create_task(limiter.acquire(phase="initial"))
        await asyncio.sleep(0)
        self.assertFalse(blocked_normal.done())

        await asyncio.wait_for(limiter.acquire(phase="final"), timeout=0.1)
        self.assertEqual(limiter.active, 3)
        self.assertEqual(limiter.normal_active, 2)

        limiter.release(phase="final")
        self.assertFalse(blocked_normal.done())
        limiter.release(phase="initial")
        await asyncio.wait_for(blocked_normal, timeout=0.1)

        limiter.release(phase="initial")
        limiter.release(phase="initial")
        self.assertEqual(limiter.active, 0)
        self.assertEqual(limiter.normal_active, 0)

    async def test_cancelled_priority_waiter_does_not_leak_slot(self) -> None:
        http_client = OrderedHTTPClient()
        client = LunitModelClient(
            FakeSettings(upstream_retries=0, upstream_concurrency=1),
            http_client=http_client,
        )
        client._upstream_limiter = _PriorityLimiter(capacity=1)
        holder = asyncio.create_task(
            client.chat([{"role": "user", "content": "holder"}])
        )
        await asyncio.wait_for(http_client.first_started.wait(), timeout=1.0)

        priority = asyncio.create_task(
            client.chat(
                [{"role": "user", "content": "cancelled-priority"}],
                phase="final",
            )
        )
        normal = asyncio.create_task(
            client.chat([{"role": "user", "content": "normal"}])
        )
        await asyncio.sleep(0)
        priority.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await priority

        http_client.release_first.set()
        await asyncio.wait_for(asyncio.gather(holder, normal), timeout=1.0)
        extra = await asyncio.wait_for(
            client.chat([{"role": "user", "content": "extra"}]),
            timeout=1.0,
        )

        self.assertEqual(extra["content"], "ok")
        self.assertEqual(http_client.order, ["holder", "normal", "extra"])

    async def test_cancelled_granted_waiter_reclaims_reserved_slot(self) -> None:
        limiter = _PriorityLimiter(capacity=1)
        await limiter.acquire(phase="initial")
        waiter = asyncio.create_task(limiter.acquire(phase="final"))
        await asyncio.sleep(0)

        # Grant the queued waiter, then cancel before it can resume from await.
        limiter.release()
        waiter.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await waiter

        await asyncio.wait_for(limiter.acquire(phase="initial"), timeout=1.0)
        self.assertEqual(limiter.active, 1)
        limiter.release()
        self.assertEqual(limiter.active, 0)

    async def test_max_retries_zero_overrides_settings(self) -> None:
        http_client = SequenceHTTPClient(
            [FakeResponse(500), FakeResponse(200)]
        )
        client = LunitModelClient(
            FakeSettings(upstream_retries=2),
            http_client=http_client,
        )

        with patch(
            "src.model_client.asyncio.sleep", new_callable=AsyncMock
        ) as sleep:
            with self.assertRaises(UpstreamError):
                await client.chat(
                    [{"role": "user", "content": "question"}],
                    max_retries=0,
                )

        self.assertEqual(http_client.calls, 1)
        sleep.assert_not_awaited()

    async def test_retry_is_skipped_when_full_attempt_cannot_fit_deadline(
        self,
    ) -> None:
        http_client = SequenceHTTPClient(
            [FakeResponse(500), FakeResponse(200)]
        )
        client = LunitModelClient(FakeSettings(), http_client=http_client)
        deadline = asyncio.get_running_loop().time() + 0.5

        with patch(
            "src.model_client.asyncio.sleep", new_callable=AsyncMock
        ) as sleep:
            with self.assertRaises(UpstreamError):
                await client.chat(
                    [{"role": "user", "content": "question"}],
                    retry_deadline=deadline,
                )

        self.assertEqual(http_client.calls, 1)
        sleep.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
