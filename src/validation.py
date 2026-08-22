from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from src.schemas import ResolvedEvidence


_CITATION_PATTERN = re.compile(r"\[(\d+)\]")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?。!?])\s+")
_GROUNDING_NGRAM_SIZE = 3
_LOW_GROUNDING_THRESHOLD = 0.2


@dataclass(frozen=True, slots=True)
class CitationValidationResult:
    unknown_citations: list[str]
    missing_citation_despite_evidence: bool

    @property
    def has_gap(self) -> bool:
        return bool(self.unknown_citations) or self.missing_citation_despite_evidence


@dataclass(frozen=True, slots=True)
class GroundingCheck:
    citation: str
    overlap_ratio: float
    low_grounding: bool


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


def _char_ngrams(text: str, n: int = _GROUNDING_NGRAM_SIZE) -> set[str]:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    if len(normalized) < n:
        return {normalized} if normalized else set()
    return {normalized[i : i + n] for i in range(len(normalized) - n + 1)}


def _flatten_text(value: Any) -> str:
    parts: list[str] = []

    def walk(current: Any) -> None:
        if isinstance(current, dict):
            for child in current.values():
                walk(child)
        elif isinstance(current, list):
            for child in current:
                walk(child)
        elif isinstance(current, str):
            parts.append(current)

    walk(value)
    return " ".join(parts)


def assess_citation_grounding(
    content: str, evidence: list[ResolvedEvidence]
) -> list[GroundingCheck]:
    """Observation-only lexical overlap between each cited claim and its evidence.

    This never changes the answer. It is a cheap character-trigram containment
    proxy for whether the sentence next to a citation label plausibly restates
    that evidence's text, aimed at the citation-hallucination pattern in wiki 06
    (a model citing a real, retrieved source while ignoring what it actually
    says). The threshold and n-gram size are heuristic starting points, not
    calibrated against labeled data, so callers should log results rather than
    act on them until enough telemetry accumulates.
    """
    if not evidence:
        return []
    evidence_text = {item.citation: _flatten_text(item.payload) for item in evidence}
    checks: list[GroundingCheck] = []
    for sentence in _SENTENCE_BOUNDARY.split(content):
        labels = _CITATION_PATTERN.findall(sentence)
        if not labels:
            continue
        claim = _CITATION_PATTERN.sub("", sentence).strip()
        if not claim:
            continue
        claim_grams = _char_ngrams(claim)
        for label in dict.fromkeys(labels):
            citation = f"[{label}]"
            text = evidence_text.get(citation)
            if text is None:
                continue
            evidence_grams = _char_ngrams(text)
            ratio = (
                len(claim_grams & evidence_grams) / len(claim_grams)
                if claim_grams
                else 0.0
            )
            checks.append(
                GroundingCheck(
                    citation=citation,
                    overlap_ratio=round(ratio, 3),
                    low_grounding=ratio < _LOW_GROUNDING_THRESHOLD,
                )
            )
    return checks
