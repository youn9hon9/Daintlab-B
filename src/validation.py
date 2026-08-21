from __future__ import annotations

import re
from dataclasses import dataclass
from src.schemas import ResolvedEvidence


_CITATION_PATTERN = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True, slots=True)
class CitationValidationResult:
    unknown_citations: list[str]
    missing_citation_despite_evidence: bool

    @property
    def has_gap(self) -> bool:
        return bool(self.unknown_citations) or self.missing_citation_despite_evidence


def validate_answer(
    content: str, evidence: list[ResolvedEvidence], status: str
) -> CitationValidationResult:
    used_labels = {f"[{n}]" for n in _CITATION_PATTERN.findall(content)}
    valid_labels = {item.citation for item in evidence}
    unknown = sorted(
        used_labels - valid_labels,
        key=lambda label: int(label.strip("[]")),
    )
    missing = status in ("sufficient", "partial") and bool(evidence) and not used_labels
    return CitationValidationResult(
        unknown_citations=unknown,
        missing_citation_despite_evidence=missing,
    )


def remove_unknown_citations(
    content: str, result: CitationValidationResult
) -> str:
    cleaned = content
    for label in result.unknown_citations:
        cleaned = cleaned.replace(label, "")
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()
