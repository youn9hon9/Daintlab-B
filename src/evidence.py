from __future__ import annotations

import json
import re
from typing import Any

from src.schemas import CitationSelection, ResolvedEvidence, RetrievalEnvelope


_EXPLICIT_CITE_PATTERN = re.compile(
    r"cite_uid(?:[\"']?\s*[:=]\s*|\s+)[\"']?"
    r"(cite-[A-Za-z0-9][A-Za-z0-9_-]*)",
    re.IGNORECASE,
)


def extract_cite_uids(value: Any) -> list[str]:
    found: list[str] = []

    def walk(current: Any) -> None:
        if isinstance(current, dict):
            uid = current.get("cite_uid")
            if isinstance(uid, str) and uid:
                found.append(uid)
            for child in current.values():
                walk(child)
            return
        if isinstance(current, list):
            for child in current:
                walk(child)
            return
        if not isinstance(current, str):
            return
        stripped = current.strip()
        if stripped.startswith(("{", "[")):
            try:
                decoded = json.loads(stripped)
            except ValueError:
                decoded = None
            if decoded is not None and decoded != current:
                walk(decoded)
        found.extend(_EXPLICIT_CITE_PATTERN.findall(current))

    walk(value)
    return list(dict.fromkeys(found))


class EvidenceRegistry:
    def __init__(self, max_chars: int, max_items: int | None = None) -> None:
        self.max_chars = max_chars
        self.max_items = None if max_items is None else max(0, max_items)
        self._items: dict[str, dict[str, Any]] = {}

    def capture(self, source_tool: str, payload: Any) -> None:
        self._walk(source_tool, payload)

    def _walk(self, source_tool: str, value: Any) -> None:
        if isinstance(value, dict):
            uid = value.get("cite_uid")
            if isinstance(uid, str) and uid:
                self._items.setdefault(
                    uid,
                    {"source_tool": source_tool, "payload": value},
                )
            for child in value.values():
                self._walk(source_tool, child)
            return

        if isinstance(value, list):
            for child in value:
                self._walk(source_tool, child)
            return

        if not isinstance(value, str):
            return

        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                decoded = json.loads(stripped)
            except ValueError:
                decoded = None
            if decoded is not None and decoded != value:
                self._walk(source_tool, decoded)

        for uid in _EXPLICIT_CITE_PATTERN.findall(value):
            self._items.setdefault(
                uid,
                {
                    "source_tool": source_tool,
                    "payload": {"content": value},
                },
            )

    def resolve(self, selection: CitationSelection) -> RetrievalEnvelope:
        if selection.status == "no_evidence":
            return RetrievalEnvelope(status="no_evidence", note=selection.note)

        evidence: list[ResolvedEvidence] = []
        missing: list[str] = []
        seen: set[str] = set()
        remaining = self.max_chars
        item_limit_reached = False

        for item in selection.items:
            if item.cite_uid in seen:
                continue
            seen.add(item.cite_uid)
            if self.max_items is not None and len(evidence) >= self.max_items:
                item_limit_reached = True
                break
            stored = self._items.get(item.cite_uid)
            if stored is None:
                missing.append(item.cite_uid)
                continue

            payload, used = self._bounded_payload(stored["payload"], remaining)
            remaining = max(0, remaining - used)
            evidence.append(
                ResolvedEvidence(
                    citation=f"[{len(evidence) + 1}]",
                    cite_uid=item.cite_uid,
                    relevance_score=item.relevance_score,
                    source_tool=stored["source_tool"],
                    payload=payload,
                )
            )
            if remaining == 0:
                break

        notes = [selection.note] if selection.note else []
        if missing:
            notes.append(f"Ignored {len(missing)} unverified cite_uid value(s).")
        selected_uid_count = len(
            {item.cite_uid for item in selection.items}
        )
        if item_limit_reached:
            notes.append(
                f"Limited evidence to {self.max_items} selected item(s)."
            )

        if not evidence:
            return RetrievalEnvelope(
                status="no_evidence",
                note=" ".join(notes) or "No selected citation matched a tool result.",
            )

        status = selection.status
        if missing or len(evidence) < selected_uid_count:
            status = "partial"
        return RetrievalEnvelope(
            status=status,
            note=" ".join(notes),
            evidence=evidence,
        )

    @staticmethod
    def _bounded_payload(payload: Any, limit: int) -> tuple[Any, int]:
        if limit <= 0:
            return {"truncated": True, "content": ""}, 0
        serialized = json.dumps(payload, ensure_ascii=False, default=str)
        if len(serialized) <= limit:
            return payload, len(serialized)
        return {
            "truncated": True,
            "content": serialized[:limit],
        }, limit
