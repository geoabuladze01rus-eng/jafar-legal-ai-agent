from __future__ import annotations

from typing import Any, Protocol

from .action_approval import ActionApprovalRepository, ActionRequest
from .action_reconciliation import (
    ActionReconciliationService,
    ReconciliationAuditRepository,
    ReconciliationDecision,
    validate_reconciliation_inputs,
)


class SupabaseClient(Protocol):
    def rpc(self, function: str, params: dict[str, Any]) -> Any: ...


class SupabaseActionReconciliationService(ActionReconciliationService):
    """Production reconciliation using one database transaction for state + audit."""

    def __init__(
        self,
        repository: ActionApprovalRepository,
        audit_repository: ReconciliationAuditRepository,
        *,
        client: SupabaseClient,
        owner_user_id: str,
    ) -> None:
        super().__init__(repository, audit_repository=audit_repository)
        owner = owner_user_id.strip()
        if not owner:
            raise ValueError("owner_user_id_required")
        self.client = client
        self.owner_user_id = owner

    def reconcile(
        self,
        action_id: str,
        *,
        decision: ReconciliationDecision,
        operator_id: str,
        evidence_note: str,
    ) -> ActionRequest:
        action, operator, note = validate_reconciliation_inputs(
            action_id=action_id,
            operator_id=operator_id,
            evidence_note=evidence_note,
        )

        self.client.rpc(
            "reconcile_action_for_owner",
            {
                "p_owner_user_id": self.owner_user_id,
                "p_action_id": action,
                "p_decision": decision.value,
                "p_operator_id": operator,
                "p_evidence_note": note,
            },
        ).execute()

        updated = self.repository.get(action)
        if updated is None:
            raise RuntimeError("reconciled_action_missing_after_rpc")
        return updated
