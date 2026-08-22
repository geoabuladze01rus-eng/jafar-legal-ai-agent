from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    claim: str
    source: str
    source_url: str | None
    observed_at: str
    confidence: float
    raw: dict[str, Any]


class EvidenceLayer:
    """Attaches provenance to every material finding produced by Jafar."""

    def record(self, *, claim: str, source: str, source_url: str | None, confidence: float, raw: dict[str, Any]) -> EvidenceRecord:
        return EvidenceRecord(
            claim=claim,
            source=source,
            source_url=source_url,
            observed_at=datetime.now(timezone.utc).isoformat(),
            confidence=max(0.0, min(1.0, confidence)),
            raw=dict(raw),
        )

    @staticmethod
    def export(records: list[EvidenceRecord]) -> list[dict[str, Any]]:
        return [
            {
                "claim": item.claim,
                "source": item.source,
                "source_url": item.source_url,
                "observed_at": item.observed_at,
                "confidence": item.confidence,
                "raw": item.raw,
            }
            for item in records
        ]
