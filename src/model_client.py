from __future__ import annotations

import asyncio
import json
import logging
import math
import random
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, AsyncIterator, Literal

import httpx2

from src.config import Settings
from src.errors import UpstreamError, UpstreamProtocolError


_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
logger = logging.getLogger(__name__)
ModelPhase = Literal["initial", "retrieval", "final"]


def _input_metrics(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
) -> tuple[int, int, int, int]:
    return (
        len(messages),
        len(json.dumps(messages, ensure_ascii=False, separators=(",", ":"))),
        len(tools or []),
        len(json.dumps(tools or [], ensure_ascii=False, separators=(",", ":"))),
    )


@dataclass(slots=True)
class _Waiter:
    future: asyncio.Future[None]
    phase: ModelPhase
    granted: bool = False


class _PriorityLimiter:
    """Cancellation-safe capacity limiter with phase-aware wakeups.

    ``capacity`` limits initial and retrieval calls. Reserved final slots are
    additional, so direct-answer throughput is preserved while final RAG calls
    can start. Within normal capacity, retrieval continuations are admitted
    before newly queued initial calls to avoid breadth-first starvation.
    State transitions contain no awaits, so they are atomic within the single
    asyncio event loop used by the shared model client.
    """

    def __init__(
        self,
        capacity: int,
        *,
        reserved_priority_slots: int = 0,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        if reserved_priority_slots < 0:
            raise ValueError("reserved_priority_slots must not be negative")
        self.normal_capacity = capacity
        self.capacity = capacity + reserved_priority_slots
        self.active = 0
        self.normal_active = 0
        self._final_waiters: deque[_Waiter] = deque()
        self._retrieval_waiters: deque[_Waiter] = deque()
        self._initial_waiters: deque[_Waiter] = deque()

    async def acquire(self, *, phase: ModelPhase) -> None:
        waiter = _Waiter(
            asyncio.get_running_loop().create_future(),
            phase=phase,
        )
        queue = self._queue_for(phase)
        queue.append(waiter)
        self._grant_waiters()
        try:
            await waiter.future
        except BaseException:
            if waiter.granted:
                # Cancellation can race with set_result() before the task resumes.
                # Reclaim the reserved slot and hand it to the next live waiter.
                self._mark_released(phase)
                self._grant_waiters()
            else:
                try:
                    queue.remove(waiter)
                except ValueError:
                    pass
                waiter.future.cancel()
            raise

    def release(self, *, phase: ModelPhase = "initial") -> None:
        if self.active <= 0:
            raise RuntimeError("L2 limiter released without an active slot")
        self._mark_released(phase)
        self._grant_waiters()

    def _grant_waiters(self) -> None:
        while True:
            waiter = self._next_grantable_waiter()
            if waiter is None:
                return
            waiter.granted = True
            self._mark_granted(waiter.phase)
            waiter.future.set_result(None)

    def _next_grantable_waiter(self) -> _Waiter | None:
        if self.active >= self.capacity:
            return None
        final = self._pop_live(self._final_waiters)
        if final is not None:
            return final
        if self.normal_active >= self.normal_capacity:
            return None
        retrieval = self._pop_live(self._retrieval_waiters)
        if retrieval is not None:
            return retrieval
        return self._pop_live(self._initial_waiters)

    def _queue_for(self, phase: ModelPhase) -> deque[_Waiter]:
        if phase == "final":
            return self._final_waiters
        if phase == "retrieval":
            return self._retrieval_waiters
        if phase == "initial":
            return self._initial_waiters
        raise ValueError(f"Unknown L2 phase: {phase}")

    @staticmethod
    def _pop_live(queue: deque[_Waiter]) -> _Waiter | None:
        while queue:
            waiter = queue.popleft()
            if not waiter.future.done():
                return waiter
        return None

    def _mark_granted(self, phase: ModelPhase) -> None:
        self.active += 1
        if phase != "final":
            self.normal_active += 1

    def _mark_released(self, phase: ModelPhase) -> None:
        if phase != "final" and self.normal_active <= 0:
            raise RuntimeError("L2 normal limiter released without an active slot")
        self.active -= 1
        if phase != "final":
            self.normal_active -= 1

    @asynccontextmanager
    async def slot(self, *, phase: ModelPhase) -> AsyncIterator[float]:
        loop = asyncio.get_running_loop()
        started = loop.time()
        await self.acquire(phase=phase)
        wait_seconds = loop.time() - started
        try:
            yield wait_seconds
        finally:
            self.release(phase=phase)


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
        # One client instance is shared by every request handled by the app. The
        # limiter bounds only active HTTP attempts, not retry backoff sleeps. One
        # extra slot prevents queued direct calls from consuming the final-answer
        # deadline reserved by a RAG request.
        self._upstream_limiter = _PriorityLimiter(
            settings.upstream_concurrency,
            reserved_priority_slots=settings.upstream_priority_slots,
        )
        # httpx2 can terminate the process when multiple requests race through
        # the first connection setup. Serialize only that cold connection;
        # normal configured concurrency resumes after any HTTP response.
        self._cold_start_lock = asyncio.Lock()
        self._transport_warmed = False

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        phase: ModelPhase = "initial",
        max_tokens: int | None = None,
        max_retries: int | None = None,
        retry_deadline: float | None = None,
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
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        message_count, message_chars, tool_count, tool_schema_chars = (
            _input_metrics(messages, tools)
        )
        logger.info(
            "l2_input phase=%s messages=%s message_chars=%s tools=%s "
            "tool_schema_chars=%s",
            phase,
            message_count,
            message_chars,
            tool_count,
            tool_schema_chars,
        )

        endpoint = f"{self.settings.lunit_fm_api_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        logger.info(
            "l2_input phase=%s messages=%s message_chars=%s tools=%s "
            "tool_schema_chars=%s",
            phase,
            len(messages),
            len(json.dumps(messages, ensure_ascii=False, default=str)),
            len(tools) if tools else 0,
            len(json.dumps(tools, ensure_ascii=False, default=str))
            if tools
            else 0,
        )

        retry_limit = (
            self.settings.upstream_retries
            if max_retries is None
            else max(0, max_retries)
        )
        last_error: Exception | None = None
        loop = asyncio.get_running_loop()
        for attempt in range(retry_limit + 1):
            attempt_started = 0.0
            queue_wait = 0.0
            try:
                async with self._upstream_limiter.slot(
                    phase=phase
                ) as queue_wait:
                    attempt_started = loop.time()
                    try:
                        response = await self._post_with_cold_start_guard(
                            endpoint,
                            headers=headers,
                            payload=payload,
                        )
                    finally:
                        attempt_latency = loop.time() - attempt_started
            except (httpx2.TimeoutException, httpx2.TransportError) as exc:
                logger.warning(
                    "l2_attempt_failed attempt=%s phase=%s queue_wait_ms=%s "
                    "attempt_latency_ms=%s error_type=%s",
                    attempt + 1,
                    phase,
                    round(queue_wait * 1000),
                    round((loop.time() - attempt_started) * 1000)
                    if attempt_started
                    else 0,
                    type(exc).__name__,
                )
                last_error = exc
                if attempt >= retry_limit:
                    break
                if not await self._sleep_before_retry(
                    attempt,
                    phase=phase,
                    reason=type(exc).__name__,
                    deadline=retry_deadline,
                ):
                    break
                continue

            logger.info(
                "l2_attempt_complete attempt=%s phase=%s queue_wait_ms=%s "
                "attempt_latency_ms=%s status=%s",
                attempt + 1,
                phase,
                round(queue_wait * 1000),
                round(attempt_latency * 1000),
                response.status_code,
            )

            if response.status_code in _RETRYABLE_STATUS_CODES:
                last_error = UpstreamError(
                    f"Lunit FM returned HTTP {response.status_code}"
                )
                if attempt < retry_limit:
                    if not await self._sleep_before_retry(
                        attempt,
                        phase=phase,
                        reason=f"http_{response.status_code}",
                        response=response,
                        deadline=retry_deadline,
                    ):
                        break
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

    async def _post_with_cold_start_guard(
        self,
        endpoint: str,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> Any:
        if self._transport_warmed:
            return await self._client.post(
                endpoint,
                headers=headers,
                json=payload,
            )

        async with self._cold_start_lock:
            if self._transport_warmed:
                return await self._client.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                )
            response = await self._client.post(
                endpoint,
                headers=headers,
                json=payload,
            )
            self._transport_warmed = True
            return response

    async def _sleep_before_retry(
        self,
        attempt: int,
        *,
        phase: ModelPhase,
        reason: str,
        response: Any | None = None,
        deadline: float | None = None,
    ) -> bool:
        retry_after = self._retry_after_seconds(response)
        if retry_after is None:
            ceiling = min(
                self.settings.retry_max_seconds,
                self.settings.retry_base_seconds * (2**attempt),
            )
            delay = random.uniform(0.0, ceiling)
        else:
            delay = min(retry_after, self.settings.retry_max_seconds)
        if deadline is not None:
            remaining = deadline - asyncio.get_running_loop().time()
            required = delay + self.settings.upstream_timeout_seconds
            if remaining < required:
                logger.warning(
                    "l2_retry_skipped next_attempt=%s phase=%s reason=%s "
                    "remaining_ms=%s required_ms=%s",
                    attempt + 2,
                    phase,
                    reason,
                    round(max(0.0, remaining) * 1000),
                    round(required * 1000),
                )
                return False
        logger.warning(
            "l2_retry_scheduled next_attempt=%s phase=%s reason=%s "
            "delay_ms=%s",
            attempt + 2,
            phase,
            reason,
            round(delay * 1000),
        )
        await asyncio.sleep(delay)
        return True

    @staticmethod
    def _retry_after_seconds(response: Any | None) -> float | None:
        if response is None:
            return None
        headers = getattr(response, "headers", None)
        if headers is None:
            return None
        value = headers.get("Retry-After")
        if not isinstance(value, str) or not value.strip():
            return None

        value = value.strip()
        try:
            seconds = float(value)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
            except (TypeError, ValueError, OverflowError):
                return None
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            seconds = (retry_at - datetime.now(timezone.utc)).total_seconds()

        if not math.isfinite(seconds):
            return None
        return max(0.0, seconds)

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
