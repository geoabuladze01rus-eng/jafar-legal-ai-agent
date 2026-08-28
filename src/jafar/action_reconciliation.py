from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from threading import RLock
from typing import Protocol

from .action_approval import ActionApprovalRepository, ActionRequest, ActionState


class ReconciliationDecision(str, Enum):
    CONFIRMED_NOT_EXECUTED = "confirmed_not_executed"
    CONFIRMED_EXECUTED = "confirmed_executed"


@dataclass(frozen=True, slots=True)
class ReconciliationCandidate:
    action_id: str
    action_type: str
    description: str
    claimed_at: str
    claimed_by: str
    age_seconds: int
    execution_error: str | None = None


@dataclass(frozen=True, slots=True)
class ReconciliationAuditRecord:
    action_id: str
    decision: ReconciliationDecision
    operator_id: str
    evidence_note: str
    recorded_at: str


class ReconciliationAuditRepository(Protocol):
    def append(self, record: ReconciliationAuditRecord) -> None: ...

    def for_action(self, action_id: str) -> tuple[ReconciliationAuditRecord, ...]: ...


class ReconciliationAuditStore:
    """Append-only local audit trail used by tests and local development."""

    def __init__(self) -> None:
        self._records: list[ReconciliationAuditRecord] = []
        self._lock = RLock()

    def append(self, record: ReconciliationAuditRecord) -> None:
        if not record.action_id.strip() or not record.operator_id.strip() or not record.evidence_note.strip():
            raise ValueError("invalid_reconciliation_audit_record")
        with self._lock:
            self._records.append(record)

    def for_action(self, action_id: str) -> tuple[ReconciliationAuditRecord, ...]:
        with self._lock:
            return tuple(record for record in self._records if record.action_id == action_id)


class ActionReconciliationService:
    """Manual recovery boundary for actions left in ``executing`` state.

    A stale execution claim is never released automatically because the external side effect
    may already have happened even when the application failed before persisting ``executed``.
    Recovery therefore requires an explicit operator conclusion based on external evidence.
    Every successful conclusion is retained in an append-only audit trail.
    """

    def __init__(
        self,
        repository: ActionApprovalRepository,
        *,
        stale_after: timedelta = timedelta(minutes=10),
        audit_repository: ReconciliationAuditRepository | None = None,
    ) -> None:
        if stale_after <= timedelta(0):
            raise ValueError("stale_after_must_be_positive")
        self.repository = repository
        self.stale_after = stale_after
        self.audit_repository = audit_repository or ReconciliationAuditStore()

    def candidates(self, *, now: datetime | None = None) -> tuple[ReconciliationCandidate, ...]:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("now_must_be_timezone_aware")

        result: list[ReconciliationCandidate] = []
        for action in self.repository.executing():
            claimed_at = self._parse_claimed_at(action)
            age = current - claimed_at
            if age < self.stale_after:
                continue
            result.append(
                ReconciliationCandidate(
                    action_id=action.action_id,
                    action_type=action.action_type,
                    description=action.description,
                    claimed_at=action.execution_claimed_at or "",
                    claimed_by=action.execution_claimed_by or "",
                    age_seconds=max(0, int(age.total_seconds())),
                    execution_error=action.execution_error,
                )
            )
        return tuple(sorted(result, key=lambda item: (-item.age_seconds, item.action_id)))

    def reconcile(
        self,
        action_id: str,
        *,
        decision: ReconciliationDecision,
        operator_id: str,
        evidence_note: str,
    ) -> ActionRequest:
        operator = operator_id.strip()
        note = evidence_note.strip()
        if not operator:
            raise ValueError("operator_id_required")
        if not note:
            raise ValueError("reconciliation_evidence_note_required")

        action = self.repository.get(action_id)
        if action is None:
            raise KeyError(action_id)
        if action.state is not ActionState.EXECUTING:
            raise ValueError("action_not_executing")
        executor = (action.execution_claimed_by or "").strip()
        if not executor:
            raise ValueError("execution_claim_owner_missing")

        audit_reason = f"reconciliation by {operator}: {note}"
        if decision is ReconciliationDecision.CONFIRMED_NOT_EXECUTED:
            updated = self.repository.release_execution_claim(
                action_id,
                executor_id=executor,
                error=audit_reason,
            )
        elif decision is ReconciliationDecision.CONFIRMED_EXECUTED:
            updated = self.repository.mark_executed(action_id, executor_id=executor)
        else:
            raise ValueError("unsupported_reconciliation_decision")

        self.audit_repository.append(
            ReconciliationAuditRecord(
                action_id=action_id,
                decision=decision,
                operator_id=operator,
                evidence_note=note,
                recorded_at=datetime.now(timezone.utc).isoformat(),
            )
        )
        return updated

    def audit_for_action(self, action_id: str) -> tuple[ReconciliationAuditRecord, ...]:
        return self.audit_repository.for_action(action_id)

    @staticmethod
    def _parse_claimed_at(action: ActionRequest) -> datetime:
        raw = (action.execution_claimed_at or "").strip()
        if not raw:
            raise ValueError(f"execution_claim_timestamp_missing:{action.action_id}")
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"execution_claim_timestamp_invalid:{action.action_id}") from exc
        if parsed.tzinfo is None:
            raise ValueError(f"execution_claim_timestamp_naive:{action.action_id}")
        return parsed
