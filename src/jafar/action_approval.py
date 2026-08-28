from __future__ import annotations

from dataclasses import dataclass, replace
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
    decided_at: str | None = None
    decided_by: str | None = None
    decision_reason: str | None = None
    executed_at: str | None = None


class ActionApprovalStore:
    """Thread-safe state store for actions crossing the human approval boundary.

    Approved actions stay in the store so a separate execution service can consume them.
    Rejection and execution are retained for audit instead of deleting the action record.
    """

    def __init__(self) -> None:
        self._actions: dict[str, ActionRequest] = {}
        self._lock = RLock()

    def add(self, request: ActionRequest) -> None:
        if request.state is not ActionState.PROPOSED:
            raise ValueError("only_proposed_actions_can_enter_store")
        with self._lock:
            if request.action_id in self._actions:
                raise ValueError("duplicate_action_id")
            self._actions[request.action_id] = request

    def get(self, action_id: str) -> ActionRequest | None:
        with self._lock:
            return self._actions.get(action_id)

    def pending(self) -> tuple[ActionRequest, ...]:
        return self._by_state(ActionState.PROPOSED)

    def approved(self) -> tuple[ActionRequest, ...]:
        return self._by_state(ActionState.APPROVED)

    def rejected(self) -> tuple[ActionRequest, ...]:
        return self._by_state(ActionState.REJECTED)

    def executed(self) -> tuple[ActionRequest, ...]:
        return self._by_state(ActionState.EXECUTED)

    def all(self) -> tuple[ActionRequest, ...]:
        with self._lock:
            return tuple(sorted(self._actions.values(), key=self._sort_key))

    def decide(
        self,
        action_id: str,
        *,
        state: ActionState,
        decided_by: str,
        reason: str | None = None,
    ) -> ActionRequest:
        if state not in {ActionState.APPROVED, ActionState.REJECTED}:
            raise ValueError("decision_state_must_be_approved_or_rejected")
        if not decided_by.strip():
            raise ValueError("decided_by_required")
        if state is ActionState.REJECTED and not (reason or "").strip():
            raise ValueError("rejection_reason_required")

        with self._lock:
            request = self._actions.get(action_id)
            if request is None:
                raise KeyError(action_id)
            if request.state is not ActionState.PROPOSED:
                raise ValueError("action_not_pending")
            updated = replace(
                request,
                state=state,
                decided_at=datetime.now(timezone.utc).isoformat(),
                decided_by=decided_by.strip(),
                decision_reason=(reason or "").strip() or None,
            )
            self._actions[action_id] = updated
            return updated

    def mark_executed(self, action_id: str) -> ActionRequest:
        with self._lock:
            request = self._actions.get(action_id)
            if request is None:
                raise KeyError(action_id)
            if request.state is not ActionState.APPROVED:
                raise ValueError("only_approved_action_can_be_executed")
            updated = replace(
                request,
                state=ActionState.EXECUTED,
                executed_at=datetime.now(timezone.utc).isoformat(),
            )
            self._actions[action_id] = updated
            return updated

    def resolve(self, action_id: str) -> None:
        """Deprecated compatibility hook.

        Historical callers removed pending items entirely. New code must use ``decide`` so
        the decision remains auditable. Keeping this method prevents abrupt breakage while
        making accidental use explicit.
        """
        raise RuntimeError("resolve_is_deprecated_use_decide")

    def _by_state(self, state: ActionState) -> tuple[ActionRequest, ...]:
        with self._lock:
            return tuple(
                sorted(
                    (item for item in self._actions.values() if item.state is state),
                    key=self._sort_key,
                )
            )

    @staticmethod
    def _sort_key(item: ActionRequest) -> tuple[str, str]:
        return (item.created_at, item.action_id)


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
            action_id=action_id.strip(),
            action_type=action_type.strip(),
            description=description.strip(),
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
        updated = (
            self.store.decide(
                request.action_id,
                state=ActionState.APPROVED,
                decided_by=approver,
            )
            if self.store is not None
            else replace(
                request,
                state=ActionState.APPROVED,
                decided_at=datetime.now(timezone.utc).isoformat(),
                decided_by=approver.strip(),
            )
        )
        return {
            "action_id": updated.action_id,
            "state": updated.state.value,
            "approved_by": updated.decided_by,
            "decided_at": updated.decided_at,
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
        updated = (
            self.store.decide(
                request.action_id,
                state=ActionState.REJECTED,
                decided_by=approver,
                reason=reason,
            )
            if self.store is not None
            else replace(
                request,
                state=ActionState.REJECTED,
                decided_at=datetime.now(timezone.utc).isoformat(),
                decided_by=approver.strip(),
                decision_reason=reason.strip(),
            )
        )
        return {
            "action_id": updated.action_id,
            "state": updated.state.value,
            "rejected_by": updated.decided_by,
            "reason": updated.decision_reason,
            "decided_at": updated.decided_at,
        }
