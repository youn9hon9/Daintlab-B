from __future__ import annotations

import re

from src.schemas import InputMessage


_EVIDENCE_REQUIRED = re.compile(
    "|".join(
        [
            r"가이드라인|진료지침|진료기준|권고안|명시적 출처|논문|연구 결과|통계|최신|현재 기준",
            r"허가|승인|회수|공식 라벨|용량|용법|금기|상호작용|부작용 보고",
            r"급여|보험 적용|약가|법률|법령|조문|규정|고시",
            r"guideline|clinical recommendation|explicit source|citation|study result|statistics|latest|current policy",
            r"approved dose|dosage|contraindication|interaction|approval|recall|official label|adverse event report",
            r"coverage rule|insurance coverage|reimbursement|drug price|law|regulation",
        ]
    ),
    re.IGNORECASE,
)


def should_offer_retrieval(history: list[InputMessage]) -> bool:
    """Offer costly retrieval only for explicit external-evidence needs."""
    user_context = "\n".join(
        message.content for message in history if message.role == "user"
    )
    return bool(_EVIDENCE_REQUIRED.search(user_context))
