from __future__ import annotations

from typing import Any


_TOOL_GROUPS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        (
            "약물", "의약품", "복용", "투여", "용량", "부작용", "이상반응",
            "상호작용", "금기", "drug", "medication", "dose", "adverse",
            "interaction", "contraindication", "dailymed",
        ),
        ("adr_retrieve_drug_info",),
    ),
    (
        (
            "허가", "승인", "적응증", "식약처", "제품명", "성분",
            "mfds", "approval", "indication", "ingredient",
        ),
        (
            "openapi_mfds_check_drug_permission",
            "openapi_mfds_find_drugs_by_ingredient",
            "openapi_mfds_get_drug_indication",
        ),
    ),
    (
        (
            "급여", "보험", "심사평가원", "약가", "상한가", "비급여",
            "hira", "reimbursement", "coverage", "price", "off-label",
        ),
        (
            "hira_updates_search",
            "openapi_hira_get_drug_price",
        ),
    ),
    (
        (
            "의료법", "약사법", "법률", "법령", "행정규칙", "조문",
            "시행령", "시행규칙", "law.go.kr", "law", "legal",
        ),
        (
            "openapi_law_search",
            "openapi_law_list_articles",
            "openapi_law_get_article",
        ),
    ),
    (
        (
            "kcd", "질병코드", "상병코드", "진단코드", "청구코드",
            "disease code", "diagnosis code",
        ),
        (
            "kcd_search_codes",
            "kcd_get_name",
            "openapi_hira_disease_check_code",
        ),
    ),
    (
        (
            "가이드라인", "지침", "권고", "목표치", "학회", "consensus",
            "guideline", "recommendation",
        ),
        (
            "index_get_relevant_nodes",
            "index_get_page_content",
            "index_keyword_search",
        ),
    ),
    (
        (
            "논문", "연구", "근거", "최신", "출처", "인용", "pubmed",
            "evidence", "study", "research", "citation", "source",
        ),
        (
            "rag_vector_query",
            "rag_get_data_source_detail",
        ),
    ),
)

_FALLBACK_PRIORITY = (
    "rag_vector_query",
    "rag_get_data_source_detail",
    "index_get_relevant_nodes",
    "index_get_page_content",
    "index_keyword_search",
    "adr_retrieve_drug_info",
)


def select_retrieval_tools(
    query: str,
    tools: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """Return a small, query-relevant subset while preserving live schemas."""
    by_name = {
        tool["function"]["name"]: tool
        for tool in tools
        if isinstance(tool.get("function"), dict)
        and isinstance(tool["function"].get("name"), str)
    }
    normalized = query.casefold()
    selected_names: list[str] = []

    for keywords, group_names in _TOOL_GROUPS:
        if any(keyword in normalized for keyword in keywords):
            selected_names.extend(group_names)

    if not selected_names:
        selected_names.extend(_FALLBACK_PRIORITY)

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name in selected_names:
        if name in seen or name not in by_name:
            continue
        selected.append(by_name[name])
        seen.add(name)
        if len(selected) >= limit:
            break

    if selected:
        return selected

    # Unknown or newly introduced server tools: retain a bounded live fallback.
    return tools[:limit]
