from __future__ import annotations

import re

from src.schemas import InputMessage


_EVIDENCE_REQUIRED = re.compile(
    "|".join(
        [
            r"가이드라인|지침|진료기준|권고안|근거|출처|논문|연구|통계|최신",
            r"용량|용법|금기|상호작용|허가|승인|회수|안전성|부작용 보고",
            r"급여|보험|약가|법률|법령|조문|규정|고시|정책",
            r"guideline|recommendation|evidence|source|citation|study|trial|statistics|latest|current",
            r"dose|dosage|contraindication|interaction|approval|recall|label|adverse event",
            r"coverage|insurance|reimbursement|law|regulation|policy",
        ]
    ),
    re.IGNORECASE,
)


def should_offer_retrieval(history: list[InputMessage]) -> bool:
    """Offer costly retrieval only for questions needing external evidence."""
    user_context = "\n".join(
        message.content for message in history if message.role == "user"
    )
    return bool(_EVIDENCE_REQUIRED.search(user_context))
