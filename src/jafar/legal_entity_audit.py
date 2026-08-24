from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .legal_entity_adapters import SourceResult
from .legal_entity_intelligence import EntityQuery


@dataclass(frozen=True, slots=True)
class AuditRecord:
    query: str
    query_type: str
    source_key: str
    status: str
    checked_at: str
    source_url: str | None
    error: str | None


def build_audit_records(query: EntityQuery, results: list[SourceResult]) -> list[AuditRecord]:
    checked_at = datetime.now(UTC).isoformat()
    return [
        AuditRecord(
            query=query.value,
            query_type=query.query_type,
            source_key=result.source_key,
            status=result.status,
            checked_at=checked_at,
            source_url=result.source_url,
            error=result.error,
        )
        for result in results
    ]


def audit_payload(records: list[AuditRecord]) -> list[dict[str, Any]]:
    return [record.__dict__ for record in records]
