from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from src.config import Settings
from src.deterministic_router import Route
from src.mcp_gateway import MCPGateway
from src.schemas import CompiledEvidenceItem, EvidencePacket


logger = logging.getLogger(__name__)


_MAX_EVIDENCE_ITEMS = 2
_MAX_EXCERPT_CHARS = 900

# Candidate argument field names to try, in order, when filling a tool call's
# primary free-text query. The live JSON schema (fetched per request via
# gateway.list_openai_tools()) decides which candidate actually applies --
# this repo has no offline copy of the 20 MCP tools' exact parameter names,
# only mcp-tools.md's prose descriptions, so argument filling is best-effort
# and any tool call that can't find a plausible field is skipped rather than
# guessed blindly.
_QUERY_FIELD_CANDIDATES = (
    "query",
    "keyword",
    "name",
    "product_name",
    "law_name",
    "search_term",
    "term",
)
_TITLE_FIELD_CANDIDATES = ("title", "document_title", "name", "law_name")
_DATE_FIELD_CANDIDATES = (
    "date",
    "effective_date",
    "enforcement_date",
    "updated_at",
    "시행일자",
)
_SOURCE_FIELD_CANDIDATES = ("source", "url", "link", "source_url")
_EXCERPT_FIELD_CANDIDATES = ("content", "text", "excerpt", "summary", "snippet")
_MST_FIELD_CANDIDATES = ("mst", "MST", "law_mst", "law_serial_no", "serial_no")


def _first_string_field(item: dict[str, Any], candidates: tuple[str, ...]) -> str:
    for key in candidates:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _find_cite_items(value: Any) -> list[dict[str, Any]]:
    """Walk an MCP tool payload for dicts carrying a non-empty cite_uid.

    Mirrors src/evidence.py's EvidenceRegistry._walk, but returns the whole
    dict (not just the uid) so sibling fields like title/date/content are
    available for extraction. MCP results often carry the same item twice --
    once as structured JSON, once re-encoded as a JSON string inside a
    "content" text block -- so results are deduplicated by cite_uid, keeping
    the first occurrence.
    """
    found: dict[str, dict[str, Any]] = {}

    def walk(current: Any) -> None:
        if isinstance(current, dict):
            uid = current.get("cite_uid")
            if isinstance(uid, str) and uid:
                found.setdefault(uid, current)
            for child in current.values():
                walk(child)
            return
        if isinstance(current, list):
            for child in current:
                walk(child)
            return
        if isinstance(current, str):
            stripped = current.strip()
            if stripped.startswith(("{", "[")):
                try:
                    decoded = json.loads(stripped)
                except ValueError:
                    decoded = None
                if decoded is not None and decoded != current:
                    walk(decoded)

    walk(value)
    return list(found.values())


def _compile_items(payload: Any, source_tool: str, start_index: int) -> list[CompiledEvidenceItem]:
    items: list[CompiledEvidenceItem] = []
    for raw in _find_cite_items(payload):
        excerpt = _first_string_field(raw, _EXCERPT_FIELD_CANDIDATES)[:_MAX_EXCERPT_CHARS]
        if not excerpt:
            continue
        items.append(
            CompiledEvidenceItem(
                citation=f"[{start_index + len(items) + 1}]",
                cite_uid=raw["cite_uid"],
                source_tool=source_tool,
                title=_first_string_field(raw, _TITLE_FIELD_CANDIDATES),
                date=_first_string_field(raw, _DATE_FIELD_CANDIDATES),
                excerpt=excerpt,
            )
        )
        if len(items) >= _MAX_EVIDENCE_ITEMS:
            break
    return items


def _build_arguments(
    schema: dict[str, Any] | None,
    query: str,
    extra_hints: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Best-effort argument construction from a live tool schema.

    Returns None if no plausible query field is found, signalling the
    caller to skip this tool call and fall back to direct generation
    instead of sending a guessed-wrong request.
    """
    if not schema:
        return None
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return None
    arguments: dict[str, Any] = {}
    matched_query_field = False
    for candidate in _QUERY_FIELD_CANDIDATES:
        if candidate in properties:
            arguments[candidate] = query
            matched_query_field = True
            break
    if not matched_query_field:
        required = schema.get("required")
        if isinstance(required, list):
            for name in required:
                prop = properties.get(name)
                if isinstance(prop, dict) and prop.get("type") == "string":
                    arguments[name] = query
                    matched_query_field = True
                    break
    if not matched_query_field:
        return None
    for key, value in (extra_hints or {}).items():
        if key in properties:
            arguments[key] = value
    return arguments


async def compile_evidence(
    route: Route,
    query: str,
    settings: Settings,
    gateway_factory: Callable[[Settings], Any] = MCPGateway,
) -> EvidencePacket | None:
    """Deterministically call MCP tools for `route` and extractively compile
    up to 2 citable sources. No L2 call happens anywhere in this function --
    routing, query text, tool selection, and argument construction are all
    already decided by the caller or by schema introspection here.

    Returns None on any failure (unsupported tool, schema mismatch, empty
    result, MCP error, timeout) so the caller can fall back to a direct
    answer. The caller is expected to wrap this in an overall wall-clock
    deadline (asyncio.timeout) -- this function does not enforce one itself
    beyond the gateway's own per-call mcp_tool_timeout_seconds.
    """
    if route == "direct" or not query.strip():
        return None
    try:
        async with gateway_factory(settings) as gateway:
            tools = await gateway.list_openai_tools()
            schema_by_name = {
                tool["function"]["name"]: tool["function"].get("parameters")
                for tool in tools
                if isinstance(tool.get("function"), dict)
            }
            if route == "policy_legal":
                compiled = await _compile_policy_legal(gateway, schema_by_name, query)
            elif route == "drug_dose":
                compiled = await _compile_single_hop(
                    gateway, schema_by_name, "openapi_mfds_get_drug_indication", query
                )
            else:
                compiled = await _compile_single_hop(
                    gateway,
                    schema_by_name,
                    "index_get_relevant_nodes",
                    query,
                    extra_hints={"corpus_tag": "guideline"},
                )
    except Exception as exc:
        logger.warning(
            "evidence_compiler_failed route=%s error_type=%s",
            route,
            type(exc).__name__,
        )
        return None

    if not compiled:
        return None
    return EvidencePacket(status="sufficient", items=compiled)


async def _compile_single_hop(
    gateway: Any,
    schema_by_name: dict[str, Any],
    tool_name: str,
    query: str,
    *,
    extra_hints: dict[str, str] | None = None,
) -> list[CompiledEvidenceItem]:
    if tool_name not in schema_by_name:
        logger.warning("evidence_compiler_tool_missing tool=%s", tool_name)
        return []
    arguments = _build_arguments(schema_by_name[tool_name], query, extra_hints)
    if arguments is None:
        logger.warning("evidence_compiler_no_query_field tool=%s", tool_name)
        return []
    payload, _content = await gateway.call_tool(tool_name, arguments)
    if payload.get("isError") is True:
        return []
    return _compile_items(payload, tool_name, start_index=0)


async def _compile_policy_legal(
    gateway: Any,
    schema_by_name: dict[str, Any],
    query: str,
) -> list[CompiledEvidenceItem]:
    if "openapi_law_search" not in schema_by_name:
        logger.warning("evidence_compiler_tool_missing tool=openapi_law_search")
        return []
    search_arguments = _build_arguments(schema_by_name["openapi_law_search"], query)
    if search_arguments is None:
        logger.warning(
            "evidence_compiler_no_query_field tool=openapi_law_search"
        )
        return []
    search_payload, _content = await gateway.call_tool(
        "openapi_law_search", search_arguments
    )
    if search_payload.get("isError") is True:
        return []

    search_items = _compile_items(
        search_payload, "openapi_law_search", start_index=0
    )
    if search_items:
        # The search response already carried citable content (some MCP
        # search tools return excerpts directly) -- no need for a second
        # call, staying within the 1-2 source budget.
        return search_items

    if "openapi_law_get_article" not in schema_by_name:
        return []
    mst = _find_first_matching_value(search_payload, _MST_FIELD_CANDIDATES)
    if mst is None:
        return []
    article_schema = schema_by_name["openapi_law_get_article"]
    article_properties = (
        article_schema.get("properties") if isinstance(article_schema, dict) else None
    )
    if not isinstance(article_properties, dict):
        return []
    mst_field = next(
        (name for name in _MST_FIELD_CANDIDATES if name in article_properties), None
    )
    if mst_field is None:
        return []
    article_payload, _content = await gateway.call_tool(
        "openapi_law_get_article", {mst_field: mst}
    )
    if article_payload.get("isError") is True:
        return []
    return _compile_items(article_payload, "openapi_law_get_article", start_index=0)


def _find_first_matching_value(value: Any, candidates: tuple[str, ...]) -> Any | None:
    if isinstance(value, dict):
        for key in candidates:
            if key in value and value[key] not in (None, ""):
                return value[key]
        for child in value.values():
            found = _find_first_matching_value(child, candidates)
            if found is not None:
                return found
        return None
    if isinstance(value, list):
        for child in value:
            found = _find_first_matching_value(child, candidates)
            if found is not None:
                return found
        return None
    return None
