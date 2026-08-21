from __future__ import annotations

import re
from dataclasses import dataclass


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?。!?])\s+")
_LONG_SENTENCE_CHAR_THRESHOLD = 120


@dataclass(frozen=True, slots=True)
class ReadabilityCheck:
    sentence_count: int
    long_sentence_count: int
    max_sentence_chars: int


def assess_readability(content: str) -> ReadabilityCheck:
    """Observation-only plain-language proxy (wiki 11: 가독성·공감).

    wiki 11 notes that a "write simply" prompt instruction alone doesn't
    reliably produce lay-readable output (The Biased Oracle, 2025) and
    recommends a separate post-generation check instead of piling more
    instructions into the system prompt -- the same meta-pattern behind
    every prompt-rule regression in this repo (Y3, U2, F001, F002). This
    measures the crudest available proxy, sentence character length, without
    judging medical correctness or attempting a lay-language rewrite. It
    never modifies the answer.
    """
    sentences = [s.strip() for s in _SENTENCE_BOUNDARY.split(content) if s.strip()]
    if not sentences:
        return ReadabilityCheck(
            sentence_count=0, long_sentence_count=0, max_sentence_chars=0
        )
    lengths = [len(sentence) for sentence in sentences]
    long_sentences = [
        length for length in lengths if length > _LONG_SENTENCE_CHAR_THRESHOLD
    ]
    return ReadabilityCheck(
        sentence_count=len(sentences),
        long_sentence_count=len(long_sentences),
        max_sentence_chars=max(lengths),
    )
