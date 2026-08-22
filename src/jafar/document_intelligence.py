from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    document_id: str
    content_hash: str
    text: str
    facts: tuple[dict[str, Any], ...]
    metadata: dict[str, Any]


class DocumentIntelligence:
    """Common normalization layer for PDF/DOCX/OCR/PLAUD/email-derived documents."""

    def extract(self, *, document_id: str, text: str, metadata: dict[str, Any] | None = None) -> ExtractedDocument:
        normalized = " ".join(text.split())
        facts = self._extract_facts(normalized)
        return ExtractedDocument(
            document_id=document_id,
            content_hash=sha256(normalized.encode("utf-8")).hexdigest(),
            text=normalized,
            facts=tuple(facts),
            metadata=metadata or {},
        )

    @staticmethod
    def _extract_facts(text: str) -> list[dict[str, Any]]:
        facts: list[dict[str, Any]] = []
        if not text:
            return facts
        facts.append({"type": "text", "value": text})
        return facts
