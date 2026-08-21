from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InputMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str
    messages: list[InputMessage]
    stream: bool = False


class RiskFlag(BaseModel):
    category: str
    matched_text: str
    turn_index: int


class RiskAssessment(BaseModel):
    active_categories: list[str] = Field(default_factory=list)
    flags: list[RiskFlag] = Field(default_factory=list)
    reassurance_detected: bool = False
    note: str = ""

    @property
    def has_risk(self) -> bool:
        return bool(self.active_categories)


class ResponseGuidance(BaseModel):
    clarification_needed: bool = False
    missing_context: list[str] = Field(default_factory=list)
    global_context_needed: bool = False
    note: str = ""


class CompiledEvidenceItem(BaseModel):
    """One harness-extracted, citable source (F010 evidence compiler).

    Unlike the old ResolvedEvidence, no L2 selects or scores this -- the
    harness decides inclusion deterministically, so there is no
    relevance_score or role field to carry.
    """

    citation: str
    cite_uid: str
    source_tool: str
    title: str = ""
    date: str = ""
    excerpt: str = ""


class EvidencePacket(BaseModel):
    status: Literal["sufficient", "no_evidence"]
    note: str = ""
    items: list[CompiledEvidenceItem] = Field(default_factory=list)

