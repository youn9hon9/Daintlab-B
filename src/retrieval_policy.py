from __future__ import annotations

import re

from src.schemas import InputMessage


_EXTERNAL_EVIDENCE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:guideline|guidelines|consensus|clinical protocol)\b",
        r"\b(?:cite|citation|citations|source for this|sources for this)\b",
        r"\b(?:provide|include|give|show|list|use)\s+(?:me\s+)?(?:a\s+)?(?:source|sources|citation|citations|reference|references)\b",
        r"\bwith\s+(?:sources|citations|references)\b",
        r"\b(?:search for|look up|retrieve)\b",
        r"\b(?:latest|newest|up[- ]to[- ]date)\s+(?:guideline|guidelines|recommendation|recommendations|evidence|research|study|studies|data|approval|policy|information)\b",
        r"\b(?:recent studies?|current evidence)\b",
        r"\b(?:pubmed|systematic review|meta-analysis|research evidence)\b",
        r"\b(?:fda|mfds|drug label|approved indication|approval status)\b",
        r"\b(?:reimbursement|insurance coverage|formulary|drug price|hira)\b",
        r"\b(?:law|legal|statute|regulation|regulatory requirement)\b",
        r"\b(?:kcd|icd(?:-?\d+)?|diagnosis code|billing code|disease code)\b",
        r"(?:가이드라인|진료지침|최신 근거|최신 연구|출처|인용|검색해)",
        r"(?:식약처|허가사항|허가 적응증|급여기준|보험 적용|약가|법령|조문)",
        r"(?:질병코드|진단코드|상병코드|청구코드|KCD)",
    )
)


def should_offer_retrieval(history: list[InputMessage]) -> bool:
    """Gate costly retrieval to requests that explicitly need external facts."""
    recent_user_text = "\n".join(
        message.content
        for message in history
        if message.role == "user"
    )[-6_000:]
    return any(
        pattern.search(recent_user_text)
        for pattern in _EXTERNAL_EVIDENCE_PATTERNS
    )
