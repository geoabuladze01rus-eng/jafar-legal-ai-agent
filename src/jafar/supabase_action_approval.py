from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from .action_approval import (
    ActionApprovalRepository,
    ActionRequest,
    ActionState,
    _validate_decision,
)


class SupabaseClient(Protocol):
    def table(self, name: str) -> Any: ...


class SupabaseActionApprovalRepository(ActionApprovalRepository):
    """Durable, owner-scoped approval ledger backed by Supabase.

    State transitions use conditional updates (``proposed`` -> decision and ``approved`` ->
    ``executed``) so two concurrent clients cannot both advance the same action from an old
    state. Records are never deleted by this repository.
    """

    TABLE = "action_approvals"

    def __init__(self, client: SupabaseClient, owner_user_id: str) -> None:
        owner = owner_user_id.strip()
        if not owner:
            raise ValueError("owner_user_id_required")
        self.client = client
        self.owner_user_id = owner

    def add(self, request: ActionRequest) -> None:
        if request.state is not ActionState.PROPOSED:
            raise ValueError("only_proposed_actions_can_enter_store")
        if self.get(request.action_id) is not None:
            raise ValueError("duplicate_action_id")

        payload = self._payload(request)
        payload["owner_user_id"] = self.owner_user_id
        try:
            self.client.table(self.TABLE).insert(payload).execute()
        except Exception as exc:
            if self.get(request.action_id) is not None:
                raise ValueError("duplicate_action_id") from exc
            raise

    def get(self, action_id: str) -> ActionRequest | None:
        response = (
            self.client.table(self.TABLE)
            .select("*")
            .eq("owner_user_id", self.owner_user_id)
            .eq("action_id", action_id)
            .maybe_single()
            .execute()
        )
        return self._request(response.data) if response.data else None

    def pending(self) -> tuple[ActionRequest, ...]:
        return self._by_state(ActionState.PROPOSED)

    def approved(self) -> tuple[ActionRequest, ...]:
        return self._by_state(ActionState.APPROVED)

    def rejected(self) -> tuple[ActionRequest, ...]:
        return self._by_state(ActionState.REJECTED)

    def executed(self) -> tuple[ActionRequest, ...]:
        return self._by_state(ActionState.EXECUTED)

    def all(self) -> tuple[ActionRequest, ...]:
        response = (
            self.client.table(self.TABLE)
            .select("*")
            .eq("owner_user_id", self.owner_user_id)
            .order("created_at")
            .execute()
        )
        return tuple(self._request(row) for row in response.data or [])

    def decide(
        self,
        action_id: str,
        *,
        state: ActionState,
        decided_by: str,
        reason: str | None = None,
    ) -> ActionRequest:
        _validate_decision(state=state, decided_by=decided_by, reason=reason)
        decided_at = datetime.now(timezone.utc).isoformat()
        payload = {
            "state": state.value,
            "decided_at": decided_at,
            "decided_by": decided_by.strip(),
            "decision_reason": (reason or "").strip() or None,
        }
        response = (
            self.client.table(self.TABLE)
            .update(payload)
            .eq("owner_user_id", self.owner_user_id)
            .eq("action_id", action_id)
            .eq("state", ActionState.PROPOSED.value)
            .execute()
        )
        row = self._first(response.data)
        if row is not None:
            return self._request(row)

        current = self.get(action_id)
        if current is None:
            raise KeyError(action_id)
        if (
            current.state is state
            and current.decided_by == decided_by.strip()
            and current.decision_reason == ((reason or "").strip() or None)
        ):
            return current
        raise ValueError("action_not_pending")

    def mark_executed(self, action_id: str) -> ActionRequest:
        executed_at = datetime.now(timezone.utc).isoformat()
        response = (
            self.client.table(self.TABLE)
            .update(
                {
                    "state": ActionState.EXECUTED.value,
                    "executed_at": executed_at,
                }
            )
            .eq("owner_user_id", self.owner_user_id)
            .eq("action_id", action_id)
            .eq("state", ActionState.APPROVED.value)
            .execute()
        )
        row = self._first(response.data)
        if row is not None:
            return self._request(row)

        current = self.get(action_id)
        if current is None:
            raise KeyError(action_id)
        if current.state is ActionState.EXECUTED and current.executed_at:
            return current
        raise ValueError("only_approved_action_can_be_executed")

    def _by_state(self, state: ActionState) -> tuple[ActionRequest, ...]:
        response = (
            self.client.table(self.TABLE)
            .select("*")
            .eq("owner_user_id", self.owner_user_id)
            .eq("state", state.value)
            .order("created_at")
            .execute()
        )
        return tuple(self._request(row) for row in response.data or [])

    @staticmethod
    def _first(data: Any) -> dict[str, Any] | None:
        if isinstance(data, list):
            return data[0] if data else None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _payload(request: ActionRequest) -> dict[str, Any]:
        created_at = request.created_at or datetime.now(timezone.utc).isoformat()
        return {
            "action_id": request.action_id,
            "action_type": request.action_type,
            "description": request.description,
            "requested_by": request.requested_by,
            "state": request.state.value,
            "requires_human_approval": request.requires_human_approval,
            "evidence_ids": list(request.evidence_ids),
            "created_at": created_at,
            "decided_at": request.decided_at,
            "decided_by": request.decided_by,
            "decision_reason": request.decision_reason,
            "executed_at": request.executed_at,
        }

    @staticmethod
    def _request(row: dict[str, Any]) -> ActionRequest:
        evidence = row.get("evidence_ids") or []
        return ActionRequest(
            action_id=str(row["action_id"]),
            action_type=str(row["action_type"]),
            description=str(row["description"]),
            requested_by=str(row.get("requested_by") or "jafar"),
            state=ActionState(row.get("state", ActionState.PROPOSED.value)),
            requires_human_approval=bool(row.get("requires_human_approval", True)),
            evidence_ids=tuple(str(item) for item in evidence),
            created_at=str(row.get("created_at") or ""),
            decided_at=(str(row["decided_at"]) if row.get("decided_at") else None),
            decided_by=(str(row["decided_by"]) if row.get("decided_by") else None),
            decision_reason=(
                str(row["decision_reason"]) if row.get("decision_reason") else None
            ),
            executed_at=(str(row["executed_at"]) if row.get("executed_at") else None),
        )
