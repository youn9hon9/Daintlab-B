"""Thin OpenAI-compatible entrypoint for the Lunit submission container."""

from __future__ import annotations

from typing import Any

from fastapi import Body, FastAPI, HTTPException

from src.api_contract import (
    DRIVER_MODEL_ID,
    ContractError,
    model_catalog,
    validate_request as validate_contract,
)
from src.conversation import ConversationService
from src.l2_client import L2Client, L2ConfigurationError, L2UpstreamError

app = FastAPI(title="daintlab-a", docs_url=None, redoc_url=None)


def get_l2_client() -> L2Client:
    return L2Client()


def validate_request(payload: Any) -> list[dict[str, Any]]:
    try:
        return validate_contract(payload)
    except ContractError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@app.get("/v1/models")
async def list_models() -> dict[str, Any]:
    return model_catalog()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def create_chat_completion(payload: Any = Body(...)) -> dict[str, Any]:
    messages = validate_request(payload)
    try:
        return await ConversationService(get_l2_client()).complete(messages)
    except L2ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except L2UpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ContractError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
