from __future__ import annotations

import re

from src.schemas import InputMessage, RiskAssessment, RiskFlag


_CATEGORY_PATTERNS: dict[str, list[str]] = {
    "chest_pain_cardiac": [
        r"가슴.{0,4}(답답|아프|조이|눌리|찢어지는)",
        r"왼팔.{0,4}저림",
        r"식은땀.{0,6}가슴",
        r"chest pain",
        r"chest tightness",
        r"crushing chest",
        r"heart attack",
    ],
    "stroke_signs": [
        r"한쪽.{0,4}(마비|힘.{0,2}빠지)",
        r"말이.{0,4}어눌",
        r"안면.{0,4}마비",
        r"갑자기.{0,4}시야",
        r"sudden weakness",
        r"slurred speech",
        r"face drooping",
        r"\bstroke\b",
    ],
    "breathing_difficulty": [
        r"숨.{0,4}(쉬기.{0,2}힘들|가쁘|막히)",
        r"호흡곤란",
        r"can'?t breathe",
        r"shortness of breath",
        r"gasping for air",
    ],
    "anaphylaxis_severe_allergy": [
        r"아나필락시스",
        r"목.{0,4}(부어|부풀)",
        r"두드러기.{0,6}호흡",
        r"anaphylaxis",
        r"throat swelling",
        r"severe allergic reaction",
    ],
    "severe_bleeding": [
        r"피가.{0,4}(멈추지|안.{0,2}멈)",
        r"심한.{0,4}출혈",
        r"다량.{0,4}출혈",
        r"heavy bleeding",
        r"won'?t stop bleeding",
        r"hemorrhage",
    ],
    "suicidal_selfharm": [
        r"죽고.{0,2}싶",
        r"자살",
        r"자해",
        r"\bsuicide\b",
        r"want to die",
        r"kill myself",
        r"self-harm",
    ],
    "altered_consciousness_seizure": [
        r"의식.{0,4}(잃|없)",
        r"기절",
        r"경련",
        r"발작",
        r"loss of consciousness",
        r"\bseizure\b",
        r"unresponsive",
        r"fainted",
    ],
    "severe_abdominal_pain": [
        r"참을.{0,2}수.{0,2}없.{0,4}복통",
        r"극심한.{0,4}복통",
        r"severe abdominal pain",
        r"unbearable stomach pain",
    ],
    "pediatric_infant_high_fever": [
        r"신생아.{0,6}고열",
        r"영아.{0,6}(39|40)도",
        r"newborn.{0,6}fever",
        r"infant.{0,6}fever",
    ],
    "poisoning_overdose": [
        r"약.{0,4}(과다.{0,2}복용|중독)",
        r"한꺼번에.{0,4}먹",
        r"\boverdose\b",
        r"\bpoisoning\b",
        r"took too many pills",
    ],
    "pregnancy_emergency": [
        r"임신.{0,6}(심한.{0,2}출혈|태동.{0,2}없)",
        r"pregnant.{0,6}bleeding",
        r"no fetal movement",
    ],
}

_COMPILED_CATEGORY_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    category: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    for category, patterns in _CATEGORY_PATTERNS.items()
}

_REASSURANCE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"괜찮겠죠",
        r"별거.{0,2}아니겠죠",
        r"그냥.{0,4}넘어가도",
        r"심각한.{0,2}건.{0,2}아니죠",
        r"it'?s probably nothing",
        r"i'?m sure it'?s fine",
        r"don'?t need to worry",
    ]
]


def assess_risk(history: list[InputMessage]) -> RiskAssessment:
    """Deterministically scan conversation history for red-flag categories.

    Only user-authored turns are scanned; assistant replies routinely mention
    red-flag vocabulary while explaining or reassuring, which would create
    false positives disconnected from what the patient actually reported.
    Every user turn in the full history is checked on every call, so a
    category detected on an earlier turn stays active on later turns without
    needing any session state.
    """
    active: dict[str, RiskFlag] = {}

    for turn_index, message in enumerate(history):
        if message.role != "user":
            continue
        for category, patterns in _COMPILED_CATEGORY_PATTERNS.items():
            if category in active:
                continue
            for pattern in patterns:
                match = pattern.search(message.content)
                if match:
                    active[category] = RiskFlag(
                        category=category,
                        matched_text=match.group(0),
                        turn_index=turn_index,
                    )
                    break

    reassurance_detected = False
    if active:
        user_turns = [message for message in history if message.role == "user"]
        if user_turns:
            latest = user_turns[-1].content
            reassurance_detected = any(
                pattern.search(latest) for pattern in _REASSURANCE_PATTERNS
            )

    note = ""
    if reassurance_detected:
        note = (
            "User appears to be minimizing or seeking reassurance about a "
            "previously flagged symptom; do not soften the safety guidance."
        )

    return RiskAssessment(
        active_categories=sorted(active),
        flags=list(active.values()),
        reassurance_detected=reassurance_detected,
        note=note,
    )
