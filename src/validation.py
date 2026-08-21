from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

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


def build_repair_instruction(result: CitationValidationResult) -> dict[str, Any]:
    return {
        "task": "revise_final_answer_for_citation_integrity",
        "issues": {
            "unknown_citations": result.unknown_citations,
            "missing_citation_despite_evidence": result.missing_citation_despite_evidence,
        },
        "instructions": (
            "Rewrite only the final answer text. Remove or rephrase any citation "
            "marker with no matching evidence item. If evidence exists and its "
            "status is sufficient or partial, attach a [n] citation to every "
            "claim drawn from that evidence. Do not invent new evidence or "
            "citations. Keep the same language, conclusions, and safety guidance."
        ),
    }
