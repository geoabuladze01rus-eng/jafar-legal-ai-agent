"""Safe, idempotent persistence boundary for derived matter intelligence."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .matter_intelligence_store import IntelligenceRecord, MatterIntelligenceRepository

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PersistenceOutcome:
    status: str
    records: tuple[IntelligenceRecord, ...] = ()
    error_category: str | None = None


class MatterIntelligenceWriter:
    """One application boundary for append-only intelligence writes.

    The writer never receives prompts or provider responses.  It accepts already-shaped
    structured payloads, sanitizes obvious secret fields, and converts storage failures into
    a reconciliation-friendly ``analysis_completed_persistence_pending`` outcome.
    """

    _SECRET_KEYS = frozenset({"prompt", "raw_prompt", "api_key", "service_role_key", "bearer_token", "access_token", "raw_response"})

    def __init__(self, repository: MatterIntelligenceRepository, *, logger: logging.Logger | None = None) -> None:
        self.repository = repository
        self.logger = logger or LOGGER

    def write(
        self,
        *,
        owner_id: str,
        matter_id: str,
        kind: str,
        payload: dict[str, Any],
        analysis_run_id: str,
        version: int = 1,
    ) -> PersistenceOutcome:
        try:
            safe_payload = _sanitize(payload)
            record = self.repository.append(
                owner_id=owner_id,
                matter_id=matter_id,
                kind=kind,
                payload=safe_payload,
                analysis_run_id=analysis_run_id,
                version=version,
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(
                "intelligence_persistence_pending run_id=%s matter_id=%s kind=%s failure=%s",
                analysis_run_id,
                matter_id,
                kind,
                type(exc).__name__,
            )
            return PersistenceOutcome("analysis_completed_persistence_pending", error_category=type(exc).__name__)
        self.logger.info(
            "intelligence_persisted run_id=%s matter_id=%s kind=%s count=1",
            analysis_run_id,
            matter_id,
            kind,
        )
        return PersistenceOutcome("persisted", (record,))

    def write_many(
        self,
        *,
        owner_id: str,
        matter_id: str,
        kind: str,
        payloads: list[dict[str, Any]] | tuple[dict[str, Any], ...],
        analysis_run_id: str,
        version: int = 1,
    ) -> PersistenceOutcome:
        records: list[IntelligenceRecord] = []
        for payload in payloads:
            outcome = self.write(owner_id=owner_id, matter_id=matter_id, kind=kind, payload=payload, analysis_run_id=analysis_run_id, version=version)
            if outcome.status != "persisted":
                return PersistenceOutcome(outcome.status, tuple(records), outcome.error_category)
            records.extend(outcome.records)
        return PersistenceOutcome("persisted", tuple(records))


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize(item) for key, item in value.items() if str(key).casefold() not in MatterIntelligenceWriter._SECRET_KEYS}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    return value
