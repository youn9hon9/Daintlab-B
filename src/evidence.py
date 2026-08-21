from __future__ import annotations

import json
import re
from typing import Any


_EXPLICIT_CITE_PATTERN = re.compile(
    r"cite_uid(?:[\"']?\s*[:=]\s*|\s+)[\"']?"
    r"(cite-[A-Za-z0-9][A-Za-z0-9_-]*)",
    re.IGNORECASE,
)


def extract_cite_uids(value: Any) -> list[str]:
    """Walk an MCP tool payload for cite_uid values, used by mcp_gateway.py
    to keep citable identifiers when a raw result must be truncated for size.
    """
    found: list[str] = []

    def walk(current: Any) -> None:
        if isinstance(current, dict):
            uid = current.get("cite_uid")
            if isinstance(uid, str) and uid:
                found.append(uid)
            for child in current.values():
                walk(child)
            return
        if isinstance(current, list):
            for child in current:
                walk(child)
            return
        if not isinstance(current, str):
            return
        stripped = current.strip()
        if stripped.startswith(("{", "[")):
            try:
                decoded = json.loads(stripped)
            except ValueError:
                decoded = None
            if decoded is not None and decoded != current:
                walk(decoded)
        found.extend(_EXPLICIT_CITE_PATTERN.findall(current))

    walk(value)
    return list(dict.fromkeys(found))
