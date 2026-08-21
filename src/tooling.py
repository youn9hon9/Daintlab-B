from __future__ import annotations

from typing import Any

from src.errors import UpstreamProtocolError


def validated_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Defensively validate any tool_calls L2 returns.

    F010 offers no tools to L2 at all -- routing, query construction, tool
    selection, and evidence compaction all happen in the harness before the
    single L2 call. A well-formed tool_calls entry here would mean L2
    attempted to call something it was never offered, which the caller
    treats as an upstream protocol violation rather than a normal response.
    """
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
