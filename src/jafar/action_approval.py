from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from threading import RLock
from typing import Any, Protocol


class ActionState(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    EXECUTED = "executed"


def payload_fingerprint(payload: dict[str, Any]) -> str:
    """Return a deterministic SHA-256 fingerprint for an execution payload."""

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class ActionRequest:
    action_id: str
    action_type: str
    description: str
    requested_by: str = "jafar"
    state: ActionState = ActionState.PROPOSED
    requires_human_approval: bool = True
    evidence_ids: tuple[str, ...] = ()
    payload_hash: str | None = None
    created_at: str = ""
    decided_at: str | None = None
    decided_by: str | None = None
    decision_reason: str | None = None
    execution_claimed_at: str | None = None
    execution_claimed_by: str | None = None
    execution_error: str | None = None
    executed_at: str | None = None


class ActionApprovalRepository(Protocol):
    """Persistence boundary for the human-approval lifecycle."""

    def add(self, request: ActionRequest) -> None: ...

    def get(self, action_id: str) -> ActionRequest | None: ...

    def pending(self) -> tuple[ActionRequest, ...]: ...

    def approved(self) -> tuple[ActionRequest, ...]: ...

    def rejected(self) -> tuple[ActionRequest, ...]: ...

    def executing(self) -> tuple[ActionRequest, ...]: ...

    def executed(self) -> tuple[ActionRequest, ...]: ...

    def all(self) -> tuple[ActionRequest, ...]: ...

    def decide(
        self,
        action_id: str,
        *,
        state: ActionState,
        decided_by: str,
        reason: str | None = None,
    ) -> ActionRequest: ...

    def claim_for_execution(self, action_id: str, *, executor_id: str) -> ActionRequest: ...

    def release_execution_claim(self, action_id: str, *, executor_id: str, error: str) -> ActionRequest: ...

    def mark_executed(self, action_id: str, *, executor_id: str | None = None) -> ActionRequest: ...


class ActionApprovalStore:
    """Thread-safe in-memory implementation for tests and local development."""

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

    def executing(self) -> tuple[ActionRequest, ...]:
        return self._by_state(ActionState.EXECUTING)

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
        _validate_decision(state=state, decided_by=decided_by, reason=reason)

        with self._lock:
            request = self._actions.get(action_id)
            if request is None:
                raise KeyError(action_id)
            if request.state is not ActionState.PROPOSED:
                raise ValueError("action_not_pending")
            if state is ActionState.APPROVED and not request.payload_hash:
                raise ValueError("payload_binding_required")
            updated = replace(
                request,
                state=state,
                decided_at=datetime.now(timezone.utc).isoformat(),
                decided_by=decided_by.strip(),
                decision_reason=(reason or "").strip() or None,
            )
            self._actions[action_id] = updated
            return updated

    def claim_for_execution(self, action_id: str, *, executor_id: str) -> ActionRequest:
        executor = executor_id.strip()
        if not executor:
            raise ValueError("executor_id_required")
        with self._lock:
            request = self._actions.get(action_id)
            if request is None:
                raise KeyError(action_id)
            if request.state is not ActionState.APPROVED:
                raise ValueError("action_not_available_for_execution")
            if not request.payload_hash:
                raise ValueError("payload_binding_required")
            updated = replace(
                request,
                state=ActionState.EXECUTING,
                execution_claimed_at=datetime.now(timezone.utc).isoformat(),
                execution_claimed_by=executor,
                execution_error=None,
            )
            self._actions[action_id] = updated
            return updated

    def release_execution_claim(self, action_id: str, *, executor_id: str, error: str) -> ActionRequest:
        executor = executor_id.strip()
        reason = error.strip()
        if not executor:
            raise ValueError("executor_id_required")
        if not reason:
            raise ValueError("execution_error_required")
        with self._lock:
            request = self._actions.get(action_id)
            if request is None:
                raise KeyError(action_id)
            if request.state is not ActionState.EXECUTING:
                raise ValueError("action_not_executing")
            if request.execution_claimed_by != executor:
                raise ValueError("execution_claim_owner_mismatch")
            updated = replace(
                request,
                state=ActionState.APPROVED,
                execution_claimed_at=None,
                execution_claimed_by=None,
                execution_error=reason,
            )
            self._actions[action_id] = updated
            return updated

    def mark_executed(self, action_id: str, *, executor_id: str | None = None) -> ActionRequest:
        with self._lock:
            request = self._actions.get(action_id)
            if request is None:
                raise KeyError(action_id)
            if request.state is not ActionState.EXECUTING:
                raise ValueError("only_executing_action_can_be_executed")
            if executor_id is not None and request.execution_claimed_by != executor_id.strip():
                raise ValueError("execution_claim_owner_mismatch")
            if not request.payload_hash:
                raise ValueError("payload_binding_required")
            updated = replace(
                request,
                state=ActionState.EXECUTED,
                executed_at=datetime.now(timezone.utc).isoformat(),
                execution_error=None,
            )
            self._actions[action_id] = updated
            return updated

    def resolve(self, action_id: str) -> None:
        """Deprecated compatibility hook; deletion would destroy audit history."""
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


def _validate_decision(
    *,
    state: ActionState,
    decided_by: str,
    reason: str | None,
) -> None:
    if state not in {ActionState.APPROVED, ActionState.REJECTED}:
        raise ValueError("decision_state_must_be_approved_or_rejected")
    if not decided_by.strip():
        raise ValueError("decided_by_required")
    if state is ActionState.REJECTED and not (reason or "").strip():
        raise ValueError("rejection_reason_required")


class LegalActionApprovalEngine:
    """Controls externally visible/legal actions; approval is explicit and auditable."""

    def __init__(self, store: ActionApprovalRepository | None = None) -> None:
        self.store = store

    def propose(
        self,
        *,
        action_id: str,
        action_type: str,
        description: str,
        evidence_ids: list[str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> ActionRequest:
        if not action_id.strip() or not action_type.strip() or not description.strip():
            raise ValueError("action_id_action_type_and_description_required")
        request = ActionRequest(
            action_id=action_id.strip(),
            action_type=action_type.strip(),
            description=description.strip(),
            evidence_ids=tuple(evidence_ids or ()),
            payload_hash=payload_fingerprint(payload) if payload is not None else None,
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
        if not request.payload_hash:
            raise ValueError("payload_binding_required")
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
