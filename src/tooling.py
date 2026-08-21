from __future__ import annotations

import json
from typing import Any

from src.errors import UpstreamProtocolError


RETRIEVE_TOOL = {
    "type": "function",
    "function": {
        "name": "retrieve_relevant_content",
        "description": (
            "Retrieve external evidence only when an exact guideline, current "
            "drug approval or safety fact, law, coverage rule, or explicit source "
            "is required. Make at most one retrieval request per answer. The query "
            "must be a single, self-contained question preserving all relevant "
            "patient conditions and jurisdiction or date constraints."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}


FINALIZE_TOOL = {
    "type": "function",
    "function": {
        "name": "finalize_retrieval",
        "description": (
            "Submit the final citation selection and end the retrieval phase."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["sufficient", "partial", "no_evidence"],
                },
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "cite_uid": {"type": "string", "minLength": 1},
                            "relevance_score": {"type": "number", "minimum": 0},
                        },
                        "required": ["cite_uid", "relevance_score"],
                        "additionalProperties": False,
                    },
                },
                "note": {"type": "string", "default": ""},
            },
            "required": ["status", "items"],
            "additionalProperties": False,
        },
    },
}


def parse_tool_arguments(call: dict[str, Any]) -> dict[str, Any]:
    function = call.get("function")
    if not isinstance(function, dict):
        raise ValueError("tool call is missing function")
    raw = function.get("arguments", "{}")
    if isinstance(raw, dict):
        parsed = raw
    elif isinstance(raw, str):
        parsed = json.loads(raw)
    else:
        raise ValueError("tool arguments must be a JSON object")
    if not isinstance(parsed, dict):
        raise ValueError("tool arguments must decode to an object")
    return parsed


def tool_call_name(call: dict[str, Any]) -> str:
    function = call.get("function")
    if not isinstance(function, dict) or not isinstance(function.get("name"), str):
        return ""
    return function["name"]


def assistant_message_for_history(message: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "role": "assistant",
        "content": message.get("content"),
    }
    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list):
        normalized["tool_calls"] = tool_calls
    reasoning_content = message.get("reasoning_content")
    if isinstance(reasoning_content, str):
        normalized["reasoning_content"] = reasoning_content
    return normalized


def validated_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
    raw_calls = message.get("tool_calls")
    if raw_calls is None:
        return []
    if not isinstance(raw_calls, list):
        raise UpstreamProtocolError("Lunit FM tool_calls must be an array")

    calls: list[dict[str, Any]] = []
    for call in raw_calls:
        if not isinstance(call, dict):
            raise UpstreamProtocolError("Lunit FM returned a malformed tool call")
        call_id = call.get("id")
        function = call.get("function")
        if not isinstance(call_id, str) or not call_id:
            raise UpstreamProtocolError("Lunit FM tool call has no id")
        if not isinstance(function, dict):
            raise UpstreamProtocolError("Lunit FM tool call has no function")
        if not isinstance(function.get("name"), str) or not function["name"]:
            raise UpstreamProtocolError("Lunit FM tool call has no function name")
        if not isinstance(function.get("arguments", "{}"), (str, dict)):
            raise UpstreamProtocolError(
                "Lunit FM tool call arguments must be JSON"
            )
        if call.get("type") not in (None, "function"):
            raise UpstreamProtocolError("Unsupported Lunit FM tool call type")
        calls.append(call)
    return calls


def tool_result_message(
    call: dict[str, Any], name: str, content: str
) -> dict[str, Any]:
    call_id = call.get("id")
    if not isinstance(call_id, str) or not call_id:
        raise ValueError("tool call is missing id")
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "name": name,
        "content": content,
    }


def tool_error_content(message: str) -> str:
    return json.dumps(
        {"isError": True, "error": message},
        ensure_ascii=False,
        separators=(",", ":"),
    )
