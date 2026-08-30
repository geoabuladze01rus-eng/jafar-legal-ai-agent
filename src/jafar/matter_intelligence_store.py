"""Append-only, matter-scoped persistence for intelligence results."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

INTELLIGENCE_KINDS = frozenset({"evidence", "contradiction", "authority", "council", "position", "hearing"})


@dataclass(frozen=True, slots=True)
class IntelligenceRecord:
    id: str
    owner_id: str
    matter_id: str
    kind: str
    payload: dict[str, Any]
    analysis_run_id: str
    version: int
    fingerprint: str
    created_at: datetime


class MatterIntelligenceRepository(Protocol):
    def append(self, *, owner_id: str, matter_id: str, kind: str, payload: dict[str, Any], analysis_run_id: str, version: int = 1) -> IntelligenceRecord: ...
    def list(self, *, owner_id: str, matter_id: str, kind: str, limit: int = 50) -> list[IntelligenceRecord]: ...


class MatterIntelligenceStore:
    """In-memory implementation used by local development and deterministic tests."""

    def __init__(self) -> None:
        self._records: list[IntelligenceRecord] = []

    def append(self, *, owner_id: str, matter_id: str, kind: str, payload: dict[str, Any], analysis_run_id: str, version: int = 1) -> IntelligenceRecord:
        record = _record(owner_id, matter_id, kind, payload, analysis_run_id, version)
        if any(item.fingerprint == record.fingerprint for item in self._records):
            return next(item for item in self._records if item.fingerprint == record.fingerprint)
        self._records.append(record)
        return record

    def list(self, *, owner_id: str, matter_id: str, kind: str, limit: int = 50) -> list[IntelligenceRecord]:
        return [item for item in reversed(self._records) if item.owner_id == owner_id and item.matter_id == matter_id and item.kind == kind][:limit]


class SupabaseMatterIntelligenceRepository:
    """Server-side adapter for the append-only Supabase record table."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def append(self, *, owner_id: str, matter_id: str, kind: str, payload: dict[str, Any], analysis_run_id: str, version: int = 1) -> IntelligenceRecord:
        record = _record(owner_id, matter_id, kind, payload, analysis_run_id, version)
        try:
            response = self.client.table("matter_intelligence_records").insert(_to_row(record)).execute()
        except Exception:
            existing = self.client.table("matter_intelligence_records").select("*").eq("fingerprint", record.fingerprint).maybe_single().execute()
            if getattr(existing, "data", None):
                return _from_row(existing.data)
            raise
        rows = getattr(response, "data", None) or []
        return _from_row(rows[0]) if rows else record

    def list(self, *, owner_id: str, matter_id: str, kind: str, limit: int = 50) -> list[IntelligenceRecord]:
        response = (self.client.table("matter_intelligence_records").select("*").eq("owner_id", owner_id).eq("matter_id", matter_id).eq("kind", kind).order("created_at", desc=True).limit(limit).execute())
        return [_from_row(row) for row in (getattr(response, "data", None) or [])]


def _record(owner_id: str, matter_id: str, kind: str, payload: dict[str, Any], analysis_run_id: str, version: int) -> IntelligenceRecord:
    if not owner_id.strip() or not matter_id.strip() or kind not in INTELLIGENCE_KINDS or not analysis_run_id.strip() or version < 1:
        raise ValueError("invalid_intelligence_record")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    # Run identity is trace metadata, not semantic identity: replaying one result from a
    # different request must deduplicate, while changed payloads append a new immutable record.
    fingerprint = hashlib.sha256(f"{owner_id}|{matter_id}|{kind}|{encoded}".encode()).hexdigest()
    return IntelligenceRecord(fingerprint, owner_id, matter_id, kind, dict(payload), analysis_run_id, version, fingerprint, datetime.now(UTC))


def _to_row(record: IntelligenceRecord) -> dict[str, Any]:
    return {"id": record.id, "owner_id": record.owner_id, "matter_id": record.matter_id, "kind": record.kind, "payload": record.payload, "analysis_run_id": record.analysis_run_id, "version": record.version, "fingerprint": record.fingerprint, "created_at": record.created_at.isoformat()}


def _from_row(row: dict[str, Any]) -> IntelligenceRecord:
    created = datetime.fromisoformat(str(row["created_at"]))
    return IntelligenceRecord(str(row["id"]), str(row["owner_id"]), str(row["matter_id"]), str(row["kind"]), dict(row.get("payload") or {}), str(row["analysis_run_id"]), int(row["version"]), str(row["fingerprint"]), created)
