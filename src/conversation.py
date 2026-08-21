"""Conversation application service.

This is the stable seam for future prompt, retrieval, and safety experiments.
The baseline intentionally delegates the complete ordered history directly to
L2. API and transport details stay in their respective modules.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from .api_contract import normalize_completion


class CompletionClient(Protocol):
    async def create_chat_completion(
        self, messages: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]: ...


class ConversationService:
    def __init__(self, client: CompletionClient) -> None:
        self.client = client

    async def complete(self, messages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        upstream = await self.client.create_chat_completion(messages)
        return normalize_completion(upstream)
