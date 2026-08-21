from __future__ import annotations

import json
import logging
import re
from typing import Any


logger = logging.getLogger(__name__)

_LAW_QUERY = re.compile(
    r"법률|법령|조문|의료법|약사법|law|statute|legal regulation",
    re.IGNORECASE,
)
_LAW_TOOLS = {
    "openapi_law_search",
    "openapi_law_list_articles",
    "openapi_law_get_article",
}


def select_retrieval_tools(
    query: str, tools: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], str]:
    """Reduce schemas only for a high-confidence family; otherwise fallback."""
    family = "all"
    selected = tools
    if _LAW_QUERY.search(query):
        candidates = [
            tool
            for tool in tools
            if tool.get("function", {}).get("name") in _LAW_TOOLS
        ]
        if candidates:
            selected = candidates
            family = "law"

    schema_chars = len(
        json.dumps(selected, ensure_ascii=False, separators=(",", ":"))
    )
    logger.info(
        "retrieval_tool_selection family=%s tools=%s schema_chars=%s total_tools=%s",
        family,
        len(selected),
        schema_chars,
        len(tools),
    )
    return selected, family
