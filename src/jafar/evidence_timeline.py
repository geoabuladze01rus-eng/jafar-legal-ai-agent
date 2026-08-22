from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    evidence_id: str
    kind: str
    title: str
    source: str
    occurred_at: datetime | None = None
    document_id: str | None = None
    case_id: str | None = None
    entity_ids: tuple[str, ...] = ()
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


class EvidenceTimeline:
    """Builds a chronological, source-linked evidence view for a matter."""

    def build(self, items: list[EvidenceItem]) -> dict[str, Any]:
        ordered = sorted(items, key=lambda item: item.occurred_at or datetime.min)
        return {
            "items": [self._serialize(item) for item in ordered],
            "evidence_count": len(ordered),
            "sources": sorted({item.source for item in ordered}),
            "cases": sorted({item.case_id for item in ordered if item.case_id}),
            "entities": sorted({entity for item in ordered for entity in item.entity_ids}),
        }

    @staticmethod
    def _serialize(item: EvidenceItem) -> dict[str, Any]:
        return {
            "evidence_id": item.evidence_id,
            "kind": item.kind,
            "title": item.title,
            "source": item.source,
            "occurred_at": item.occurred_at.isoformat() if item.occurred_at else None,
            "document_id": item.document_id,
            "case_id": item.case_id,
            "entity_ids": list(item.entity_ids),
            "confidence": item.confidence,
            "metadata": item.metadata,
        }
