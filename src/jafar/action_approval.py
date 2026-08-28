from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
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


class ActionApprovalStore:
    """Thread-safe inbox of legal actions waiting for an explicit human decision."""

    def __init__(self) -> None:
        self._pending: dict[str, ActionRequest] = {}
        self._lock = RLock()

    def add(self, request: ActionRequest) -> None:
        if request.state is not ActionState.PROPOSED:
            raise ValueError("only_proposed_actions_can_enter_pending_store")
        with self._lock:
            if request.action_id in self._pending:
                raise ValueError("duplicate_action_id")
            self._pending[request.action_id] = request

    def get(self, action_id: str) -> ActionRequest | None:
        with self._lock:
            return self._pending.get(action_id)

    def resolve(self, action_id: str) -> None:
        with self._lock:
            self._pending.pop(action_id, None)

    def pending(self) -> tuple[ActionRequest, ...]:
        with self._lock:
            return tuple(
                sorted(
                    self._pending.values(),
                    key=lambda item: (item.created_at, item.action_id),
                )
            )


class LegalActionApprovalEngine:
    """Controls externally visible/legal actions; approval is explicit and auditable."""

    def __init__(self, store: ActionApprovalStore | None = None) -> None:
        self.store = store

    def propose(
        self,
        *,
        action_id: str,
        action_type: str,
        description: str,
        evidence_ids: list[str] | None = None,
    ) -> ActionRequest:
        if not action_id.strip() or not action_type.strip() or not description.strip():
            raise ValueError("action_id_action_type_and_description_required")
        request = ActionRequest(
            action_id=action_id,
            action_type=action_type,
            description=description,
            evidence_ids=tuple(evidence_ids or ()),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        if self.store is not None:
            self.store.add(request)
        return request

    def approve(self, request: ActionRequest, approver: str) -> dict[str, Any]:
        if request.state is not ActionState.PROPOSED:
            raise ValueError("action_not_pending")
        if not approver.strip():
            raise ValueError("approver_required")
        if self.store is not None:
            self.store.resolve(request.action_id)
        return {
            "action_id": request.action_id,
            "state": ActionState.APPROVED.value,
            "approved_by": approver,
        }

    def reject(
        self,
        request: ActionRequest,
        approver: str,
        reason: str,
    ) -> dict[str, Any]:
        if request.state is not ActionState.PROPOSED:
            raise ValueError("action_not_pending")
        if not approver.strip() or not reason.strip():
            raise ValueError("approver_and_reason_required")
        if self.store is not None:
            self.store.resolve(request.action_id)
        return {
            "action_id": request.action_id,
            "state": ActionState.REJECTED.value,
            "rejected_by": approver,
            "reason": reason,
        }
