from __future__ import annotations

from typing import Any, Literal

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


class CitableItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cite_uid: str
    relevance_score: float = Field(ge=0.0)


class CitationSelection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["sufficient", "partial", "no_evidence"]
    items: list[CitableItem] = Field(default_factory=list)
    note: str = ""


class ResolvedEvidence(BaseModel):
    citation: str
    cite_uid: str
    relevance_score: float
    source_tool: str
    payload: Any


class RetrievalEnvelope(BaseModel):
    status: Literal["sufficient", "partial", "no_evidence"]
    note: str = ""
    evidence: list[ResolvedEvidence] = Field(default_factory=list)

