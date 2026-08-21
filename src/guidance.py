from __future__ import annotations

import re

from src.schemas import InputMessage, ResponseGuidance, RiskAssessment


def _matches(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


_SYMPTOM_QUESTION = (
    r"증상|아프|아파|아픈|통증|열이|어지|구토|설사|기침|가슴|호흡|숨.{0,4}(차|가쁘|힘들)",
    r"symptom|pain|fever|dizz|vomit|diarrhea|cough|shortness of breath",
)
_MEDICATION_QUESTION = (
    r"약.{0,6}(먹|복용|용량|부작용|바꿔|끊)|처방|투약",
    r"medication|medicine|drug|dose|dosage|side effect|prescription",
)
_PERSONAL_MARKER = (
    r"저는|제가|나는|내가|우리 아이|우리 엄마|우리 아빠|먹어도 될|해야 하나|병원.{0,4}가",
    r"\bi\b|\bmy\b|should i|can i|do i need|my child|my mother|my father",
)
_DURATION = (
    r"\d+\s*(분|시간|일|주|달|개월|년)|오늘|어제|그제|방금|아침|저녁|부터|동안|째",
    r"\d+\s*(minute|hour|day|week|month|year)s?|today|yesterday|since|for the past",
)
_SEVERITY = (
    r"경미|약간|조금|심하|극심|참을 수|악화|호전|점점|\d+\s*/\s*10",
    r"mild|moderate|severe|unbearable|worsen|improv|\d+\s*/\s*10",
)
_AGE = (
    r"\d+\s*(살|세)|신생아|영아|유아|어린이|청소년|성인|노인|고령",
    r"\d+\s*years? old|newborn|infant|child|teen|adult|elderly|older adult",
)
_CLINICAL_BACKGROUND = (
    r"임신|수유|기저질환|당뇨|고혈압|심장|신장|간질환|알레르기|복용 중|먹는 약",
    r"pregnan|breastfeed|medical history|diabetes|hypertension|heart|kidney|liver|allerg|taking",
)
_GLOBAL_CONTEXT = (
    r"비용|가격|보험|급여|보장|지원|구할 수|어디서|의료 접근|진료 가능",
    r"cost|price|insurance|coverage|available|access|where can i|get care",
)
_JURISDICTION = (
    r"한국|대한민국|미국|일본|중국|영국|캐나다|호주|유럽|국내|해외|서울|부산|제주",
    r"korea|united states|\bu\.s\.|japan|china|united kingdom|\bu\.k\.|canada|australia|europe",
)


def assess_response_guidance(
    history: list[InputMessage], risk: RiskAssessment
) -> ResponseGuidance:
    """Derive bounded response flags without generating medical advice."""
    user_messages = [message.content for message in history if message.role == "user"]
    if not user_messages:
        return ResponseGuidance()

    latest = user_messages[-1]
    full_user_context = "\n".join(user_messages)
    symptom_question = _matches(_SYMPTOM_QUESTION, latest)
    medication_question = _matches(_MEDICATION_QUESTION, latest)
    personalized = _matches(_PERSONAL_MARKER, latest)
    missing: list[str] = []

    if symptom_question and personalized:
        if not _matches(_DURATION, full_user_context):
            missing.append("onset_or_duration")
        if not _matches(_SEVERITY, full_user_context):
            missing.append("severity_or_trajectory")
        if not _matches(_AGE, full_user_context):
            missing.append("age_group")
        if not _matches(_CLINICAL_BACKGROUND, full_user_context):
            missing.append("relevant_conditions_or_medications")
    elif medication_question and personalized:
        if not _matches(_AGE, full_user_context):
            missing.append("age_group")
        if not _matches(_CLINICAL_BACKGROUND, full_user_context):
            missing.append("relevant_conditions_or_medications")

    global_context_needed = _matches(
        _GLOBAL_CONTEXT, latest
    ) and not _matches(_JURISDICTION, full_user_context)
    clarification_needed = bool(missing) and not risk.has_risk
    note = ""
    if risk.has_risk and missing:
        note = (
            "Missing context exists, but urgent action guidance must come before "
            "clarifying questions."
        )
    elif clarification_needed:
        note = (
            "Avoid a definitive personalized conclusion. Give safe interim guidance "
            "and ask only the one or two missing questions that would change action."
        )
    if global_context_needed:
        note = (
            f"{note} Ask for country or care setting, or state the jurisdiction "
            "assumed for cost, coverage, and availability claims."
        ).strip()

    return ResponseGuidance(
        clarification_needed=clarification_needed,
        missing_context=missing,
        global_context_needed=global_context_needed,
        note=note,
    )
