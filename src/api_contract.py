"""Evaluator-facing request and response contract.

This module owns validation and OpenAI-compatible response shaping only. It
must not perform network calls or contain retrieval/orchestration policy.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Mapping


DRIVER_MODEL_ID = "daintlab-a"
SUPPORTED_REQUEST_FIELDS = frozenset({"model", "messages", "stream"})
SUPPORTED_ROLES = frozenset({"system", "user", "assistant"})


@dataclass(frozen=True)
class ContractError(ValueError):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


def validate_request(payload: Any) -> list[dict[str, str]]:
    if not isinstance(payload, dict):
        raise ContractError(422, "Request body must be an object")

    unsupported = sorted(set(payload) - SUPPORTED_REQUEST_FIELDS)
    if unsupported:
        raise ContractError(400, f"Unsupported request fields: {', '.join(unsupported)}")
    if payload.get("model") != DRIVER_MODEL_ID:
        raise ContractError(400, f"model must be {DRIVER_MODEL_ID}")
    if payload.get("stream", False) is not False:
        raise ContractError(400, "Streaming is not supported")

    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ContractError(422, "messages must be a non-empty array")

    validated: list[dict[str, str]] = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ContractError(422, f"messages[{index}] must be an object")
        if set(message) != {"role", "content"}:
            raise ContractError(400, f"messages[{index}] supports only role and content")
        role, content = message.get("role"), message.get("content")
        if role not in SUPPORTED_ROLES:
            raise ContractError(422, f"messages[{index}].role is invalid")
        if not isinstance(content, str):
            raise ContractError(422, f"messages[{index}].content must be a string")
        validated.append({"role": role, "content": content})
    return validated


def model_catalog() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {
                "id": DRIVER_MODEL_ID,
                "object": "model",
                "created": 0,
                "owned_by": DRIVER_MODEL_ID,
            }
        ],
    }


def normalize_completion(result: Mapping[str, Any]) -> dict[str, Any]:
    choices = result.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ContractError(502, "L2 returned no completion choice")
    message = choices[0].get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise ContractError(502, "L2 returned an invalid assistant message")
    if not isinstance(message.get("content"), str):
        raise ContractError(502, "L2 returned invalid assistant content")

    response = dict(result)
    response["model"] = DRIVER_MODEL_ID
    response.setdefault("object", "chat.completion")
    response.setdefault("created", int(time.time()))
    return response
