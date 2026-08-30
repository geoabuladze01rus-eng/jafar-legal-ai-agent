from __future__ import annotations

from typing import Any, Protocol

from .action_reconciliation import (
    ReconciliationAuditRecord,
    ReconciliationAuditRepository,
    ReconciliationDecision,
)


class SupabaseClient(Protocol):
    def table(self, name: str) -> Any: ...


class SupabaseReconciliationAuditRepository(ReconciliationAuditRepository):
    """Owner-scoped durable append-only reconciliation audit repository."""

    TABLE = "action_reconciliation_audit"

    def __init__(self, client: SupabaseClient, owner_user_id: str) -> None:
        owner = owner_user_id.strip()
        if not owner:
            raise ValueError("owner_user_id_required")
        self.client = client
        self.owner_user_id = owner

    def append(self, record: ReconciliationAuditRecord) -> None:
        if not record.action_id.strip() or not record.operator_id.strip() or not record.evidence_note.strip():
            raise ValueError("invalid_reconciliation_audit_record")
        self.client.table(self.TABLE).insert(
            {
                "owner_user_id": self.owner_user_id,
                "action_id": record.action_id,
                "decision": record.decision.value,
                "operator_id": record.operator_id,
                "evidence_note": record.evidence_note,
                "recorded_at": record.recorded_at,
            }
        ).execute()

    def for_action(self, action_id: str) -> tuple[ReconciliationAuditRecord, ...]:
        response = (
            self.client.table(self.TABLE)
            .select("action_id,decision,operator_id,evidence_note,recorded_at")
            .eq("owner_user_id", self.owner_user_id)
            .eq("action_id", action_id)
            .order("recorded_at")
            .execute()
        )
        return tuple(
            ReconciliationAuditRecord(
                action_id=str(row["action_id"]),
                decision=ReconciliationDecision(str(row["decision"])),
                operator_id=str(row["operator_id"]),
                evidence_note=str(row["evidence_note"]),
                recorded_at=str(row["recorded_at"]),
            )
            for row in response.data or []
        )
