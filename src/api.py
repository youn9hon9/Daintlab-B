from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from src.config import Settings
from src.driver import Driver
from src.errors import ConfigurationError, UpstreamError
from src.schemas import ChatCompletionRequest


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    # docs/evaluations/TELEMETRY.md collects the candidate container's stdout.
    # logging.basicConfig defaults to stderr, and the local proxy's docker-logs
    # collection treats stderr output as an error, which silently dropped all
    # runtime_telemetry for F003. See F004 candidate notes.
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def _error_response(
    status_code: int,
    message: str,
    *,
    error_type: str,
    code: str,
) -> JSONResponse:
    return JSONResponse(
        {
            "error": {
                "message": message,
                "type": error_type,
                "param": None,
                "code": code,
            }
        },
        status_code=status_code,
    )


def create_app(
    driver: Any | None = None,
    settings: Settings | None = None,
) -> Starlette:
    resolved_settings = settings or Settings.from_env()
    resolved_driver = driver or Driver(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: Starlette):
        yield
        close = getattr(app.state.driver, "aclose", None)
        if close is not None:
            await close()

    async def list_models(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "object": "list",
                "data": [
                    {
                        "id": request.app.state.settings.driver_model_id,
                        "object": "model",
                        "owned_by": "team",
                    }
                ],
            }
        )

    async def chat_completions(request: Request) -> JSONResponse:
        request_id = f"chatcmpl-{uuid.uuid4().hex}"
        started = time.monotonic()
        try:
            payload = await request.json()
        except Exception:
            return _error_response(
                400,
                "Request body must be valid JSON.",
                error_type="invalid_request_error",
                code="invalid_json",
            )

        try:
            parsed = ChatCompletionRequest.model_validate(payload)
        except ValidationError as exc:
            fields = [".".join(map(str, item["loc"])) for item in exc.errors()]
            return _error_response(
                400,
                f"Invalid request fields: {', '.join(fields)}",
                error_type="invalid_request_error",
                code="invalid_request",
            )

        if parsed.stream:
            return _error_response(
                400,
                "Streaming responses are not supported by this driver.",
                error_type="invalid_request_error",
                code="stream_not_supported",
            )
        if not parsed.messages:
            return _error_response(
                400,
                "messages must not be empty.",
                error_type="invalid_request_error",
                code="empty_messages",
            )
        if parsed.messages[-1].role != "user":
            return _error_response(
                400,
                "The last message must have role 'user'.",
                error_type="invalid_request_error",
                code="invalid_last_role",
            )

        try:
            async with asyncio.timeout(
                request.app.state.settings.request_timeout_seconds
            ):
                answer = await request.app.state.driver.generate(parsed.messages)
        except TimeoutError:
            logger.warning("request_timed_out id=%s", request_id)
            return _error_response(
                504,
                "The driver exceeded the request time limit.",
                error_type="timeout_error",
                code="request_timeout",
            )
        except ConfigurationError as exc:
            logger.error(
                "request_failed id=%s error_type=%s",
                request_id,
                type(exc).__name__,
            )
            return _error_response(
                503,
                str(exc),
                error_type="configuration_error",
                code="driver_not_configured",
            )
        except UpstreamError as exc:
            logger.warning(
                "request_failed id=%s error_type=%s",
                request_id,
                type(exc).__name__,
            )
            return _error_response(
                502,
                str(exc),
                error_type="upstream_error",
                code="upstream_failure",
            )
        except Exception as exc:
            logger.exception(
                "request_failed id=%s error_type=%s",
                request_id,
                type(exc).__name__,
            )
            return _error_response(
                500,
                "The driver failed to generate a response.",
                error_type="server_error",
                code="internal_error",
            )

        elapsed_ms = round((time.monotonic() - started) * 1000)
        logger.info("request_complete id=%s latency_ms=%s", request_id, elapsed_ms)
        return JSONResponse(
            {
                "id": request_id,
                "object": "chat.completion",
                "created": int(time.time()),
                "model": request.app.state.settings.driver_model_id,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": answer,
                        },
                        "finish_reason": "stop",
                    }
                ],
            }
        )

    app = Starlette(
        routes=[
            Route("/v1/models", list_models, methods=["GET"]),
            Route(
                "/v1/chat/completions",
                chat_completions,
                methods=["POST"],
            ),
        ],
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.driver = resolved_driver
    return app
