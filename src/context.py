from __future__ import annotations

import re

from src.schemas import InputMessage


CONTEXT_CHAR_LIMIT = 1_000
_SPACE_RE = re.compile(r"\s+")
_GREETING_RE = re.compile(
    r"^(안녕(?:하세요)?|감사(?:합니다|해요)?|고마워(?:요)?|hello|hi|thanks)[.!? ]*$",
    re.IGNORECASE,
)
_REFERENCE_RE = re.compile(
    r"(아까|앞서|위에서|그거|그것|말한|설명한|이전 답변|above|earlier|you said|that)",
    re.IGNORECASE,
)
_CLINICAL_RE = re.compile(
    r"(증상|통증|열|기침|혈압|혈당|질환|진단|검사|약|복용|용량|수술|임신|"
    r"알레르기|남성|여성|세|일|주|개월|년|symptom|pain|fever|diagnos|test|"
    r"medication|dose|pregnan|allerg|male|female|year)",
    re.IGNORECASE,
)


def _clean(text: str) -> str:
    return _SPACE_RE.sub(" ", text).strip()


def build_oneshot_input(history: list[InputMessage]) -> tuple[str, str]:
    """Return the intact latest question and a bounded, locally selected context."""
    latest = _clean(history[-1].content)
    include_assistant = bool(_REFERENCE_RE.search(latest))
    candidates: list[tuple[int, int, str]] = []

    for index, message in enumerate(history[:-1]):
        text = _clean(message.content)
        if not text or _GREETING_RE.fullmatch(text):
            continue
        if message.role == "assistant" and not include_assistant:
            continue
        clinical = bool(_CLINICAL_RE.search(text)) or any(
            character.isdigit() for character in text
        )
        if message.role == "user" and not clinical and len(text) < 20:
            continue
        score = (3 if clinical else 0) + (2 if message.role == "user" else 0)
        candidates.append((score, index, f"{message.role}: {text}"))

    selected: list[tuple[int, str]] = []
    used = 0
    for _, index, line in sorted(candidates, key=lambda item: (item[0], item[1]), reverse=True):
        remaining = CONTEXT_CHAR_LIMIT - used
        if remaining <= 0:
            break
        bounded = line[:remaining]
        selected.append((index, bounded))
        used += len(bounded) + 1

    context = "\n".join(line for _, line in sorted(selected))
    return latest, context[:CONTEXT_CHAR_LIMIT]
