from __future__ import annotations

import re
from typing import Literal

from src.schemas import InputMessage


Route = Literal["direct", "medical_evidence", "drug_dose", "policy_legal"]


_DRUG_DOSE_PATTERNS = (
    r"용량|용법|금기|상호작용|허가.{0,4}(용량|적응증)|부작용|이상반응",
    r"\bdose\b|dosage|contraindication|drug interaction|adverse (effect|reaction)|approved indication",
)
_POLICY_LEGAL_PATTERNS = (
    r"법령|법률|조문|시행령|시행규칙|고시",
    r"급여.{0,4}(기준|적용)|보험.{0,4}(적용|기준)|약가|본인부담|삭제.{0,2}및.{0,2}적용일",
    r"\blaw\b|regulation|statute|reimbursement|insurance coverage|copay",
)
_MEDICAL_EVIDENCE_PATTERNS = (
    r"가이드라인|지침|진료기준|권고안|최신.{0,4}(연구|자료|버전|근거)",
    r"guideline|recommendation|consensus statement|latest evidence",
)

# Order matters: a message can match more than one category (e.g. a drug
# name plus "허가" also looks like policy). Check the most specific,
# single-tool-answerable category first so ambiguous messages don't fall
# through to the more expensive multi-call policy_legal route by accident.
_ROUTE_PATTERNS: tuple[tuple[Route, tuple[str, ...]], ...] = (
    ("drug_dose", _DRUG_DOSE_PATTERNS),
    ("policy_legal", _POLICY_LEGAL_PATTERNS),
    ("medical_evidence", _MEDICAL_EVIDENCE_PATTERNS),
)
_COMPILED_ROUTE_PATTERNS = tuple(
    (route, tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns))
    for route, patterns in _ROUTE_PATTERNS
)


def classify_route(history: list[InputMessage]) -> Route:
    """Deterministically classify the conversation into one of four routes.

    No L2 call is involved. Scans every user turn (not just the latest) so
    an entity established earlier in a multi-turn conversation still counts
    -- matching the existing scanning approach in src/safety.py and the old
    src/routing.py. Low-confidence or ambiguous messages default to
    "direct": a missed evidence opportunity costs completeness on one
    answer, while a wrong evidence route wastes the single MCP/L2 budget
    entirely and risks a worse answer than skipping evidence.
    """
    user_text = "\n".join(
        message.content for message in history if message.role == "user"
    )
    if not user_text.strip():
        return "direct"
    for route, patterns in _COMPILED_ROUTE_PATTERNS:
        if any(pattern.search(user_text) for pattern in patterns):
            return route
    return "direct"


_AGE_PATTERN = re.compile(r"\d+\s*(?:살|세)|\d+\s*years?\s*old", re.IGNORECASE)
_DURATION_PATTERN = re.compile(
    r"\d+\s*(?:분|시간|일|주|개월|년)|\d+\s*(?:minute|hour|day|week|month|year)s?",
    re.IGNORECASE,
)
_DOSE_PATTERN = re.compile(
    r"\d+\s*(?:mg|g|ml|mcg|정|캡슐|회)", re.IGNORECASE
)
_SELF_CONTAINED_LENGTH_THRESHOLD = 40


def build_query(history: list[InputMessage]) -> str:
    """Build a self-contained free-text query without an L2 call.

    This is a coarse proxy for the self-contained-query rewriting the old
    Retrieval L2 used to do. True cross-turn entity linking needs either an
    NLP model or an L2 call, both excluded by design (L2 must not be used
    for query generation). The heuristic: if the latest user turn already
    contains an explicit entity marker (age/duration/dose) or is long enough
    to plausibly stand alone, use it as-is; otherwise prepend the previous
    user turn for context. This will occasionally under- or over-include
    context on turns the heuristic misjudges -- a known, disclosed limit.
    """
    user_messages = [
        message.content for message in history if message.role == "user"
    ]
    if not user_messages:
        return ""
    latest = user_messages[-1].strip()
    if len(user_messages) == 1:
        return latest
    looks_self_contained = (
        _AGE_PATTERN.search(latest) is not None
        or _DURATION_PATTERN.search(latest) is not None
        or _DOSE_PATTERN.search(latest) is not None
        or len(latest) > _SELF_CONTAINED_LENGTH_THRESHOLD
    )
    if looks_self_contained:
        return latest
    previous = user_messages[-2].strip()
    return f"{previous} {latest}".strip()
