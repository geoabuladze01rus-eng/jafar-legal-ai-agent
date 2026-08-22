from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ActionState(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"


@dataclass(frozen=True, slots=True)
class ActionRequest:
    action_id: str
    action_type: str
    description: str
    requested_by: str = "jafar"
    state: ActionState = ActionState.PROPOSED
    requires_human_approval: bool = True
    evidence_ids: tuple[str, ...] = ()
    created_at: str = ""


class LegalActionApprovalEngine:
    """Controls externally visible/legal actions; approval is explicit and auditable."""

    def propose(self, *, action_id: str, action_type: str, description: str, evidence_ids: list[str] | None = None) -> ActionRequest:
        return ActionRequest(
            action_id=action_id,
            action_type=action_type,
            description=description,
            evidence_ids=tuple(evidence_ids or ()),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def approve(self, request: ActionRequest, approver: str) -> dict[str, Any]:
        if not approver.strip():
            raise ValueError("approver_required")
        return {"action_id": request.action_id, "state": ActionState.APPROVED.value, "approved_by": approver}

    def reject(self, request: ActionRequest, approver: str, reason: str) -> dict[str, Any]:
        if not approver.strip() or not reason.strip():
            raise ValueError("approver_and_reason_required")
        return {"action_id": request.action_id, "state": ActionState.REJECTED.value, "rejected_by": approver, "reason": reason}
