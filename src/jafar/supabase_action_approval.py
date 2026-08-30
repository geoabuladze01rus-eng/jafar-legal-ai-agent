from __future__ import annotations

from datetime import UTC, datetime
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

    State transitions use conditional updates so only one executor can atomically claim an
    approved action. Records are never deleted. Execution payload fingerprints are immutable.
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

    def executing(self) -> tuple[ActionRequest, ...]:
        return self._by_state(ActionState.EXECUTING)

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
        current = self.get(action_id)
        if current is None:
            raise KeyError(action_id)
        if current.state is not ActionState.PROPOSED:
            if (
                current.state is state
                and current.decided_by == decided_by.strip()
                and current.decision_reason == ((reason or "").strip() or None)
            ):
                return current
            raise ValueError("action_not_pending")
        if state is ActionState.APPROVED and not current.payload_hash:
            raise ValueError("payload_binding_required")

        decided_at = datetime.now(UTC).isoformat()
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

    def claim_for_execution(self, action_id: str, *, executor_id: str) -> ActionRequest:
        executor = executor_id.strip()
        if not executor:
            raise ValueError("executor_id_required")
        current = self.get(action_id)
        if current is None:
            raise KeyError(action_id)
        if current.state is not ActionState.APPROVED:
            raise ValueError("action_not_available_for_execution")
        if not current.payload_hash:
            raise ValueError("payload_binding_required")

        response = (
            self.client.table(self.TABLE)
            .update(
                {
                    "state": ActionState.EXECUTING.value,
                    "execution_claimed_at": datetime.now(UTC).isoformat(),
                    "execution_claimed_by": executor,
                    "execution_error": None,
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
        raise ValueError("action_not_available_for_execution")

    def release_execution_claim(self, action_id: str, *, executor_id: str, error: str) -> ActionRequest:
        executor = executor_id.strip()
        reason = error.strip()
        if not executor:
            raise ValueError("executor_id_required")
        if not reason:
            raise ValueError("execution_error_required")
        response = (
            self.client.table(self.TABLE)
            .update(
                {
                    "state": ActionState.APPROVED.value,
                    "execution_claimed_at": None,
                    "execution_claimed_by": None,
                    "execution_error": reason,
                }
            )
            .eq("owner_user_id", self.owner_user_id)
            .eq("action_id", action_id)
            .eq("state", ActionState.EXECUTING.value)
            .eq("execution_claimed_by", executor)
            .execute()
        )
        row = self._first(response.data)
        if row is not None:
            return self._request(row)
        raise ValueError("execution_claim_owner_mismatch")

    def mark_executed(self, action_id: str, *, executor_id: str | None = None) -> ActionRequest:
        current = self.get(action_id)
        if current is None:
            raise KeyError(action_id)
        if current.state is ActionState.EXECUTED and current.executed_at:
            return current
        if current.state is not ActionState.EXECUTING:
            raise ValueError("only_executing_action_can_be_executed")
        if executor_id is not None and current.execution_claimed_by != executor_id.strip():
            raise ValueError("execution_claim_owner_mismatch")
        if not current.payload_hash:
            raise ValueError("payload_binding_required")

        query = (
            self.client.table(self.TABLE)
            .update(
                {
                    "state": ActionState.EXECUTED.value,
                    "executed_at": datetime.now(UTC).isoformat(),
                    "execution_error": None,
                }
            )
            .eq("owner_user_id", self.owner_user_id)
            .eq("action_id", action_id)
            .eq("state", ActionState.EXECUTING.value)
        )
        if executor_id is not None:
            query = query.eq("execution_claimed_by", executor_id.strip())
        response = query.execute()
        row = self._first(response.data)
        if row is not None:
            return self._request(row)

        current = self.get(action_id)
        if current is not None and current.state is ActionState.EXECUTED and current.executed_at:
            return current
        raise ValueError("only_executing_action_can_be_executed")

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
        created_at = request.created_at or datetime.now(UTC).isoformat()
        return {
            "action_id": request.action_id,
            "action_type": request.action_type,
            "description": request.description,
            "requested_by": request.requested_by,
            "state": request.state.value,
            "requires_human_approval": request.requires_human_approval,
            "evidence_ids": list(request.evidence_ids),
            "payload_hash": request.payload_hash,
            "created_at": created_at,
            "decided_at": request.decided_at,
            "decided_by": request.decided_by,
            "decision_reason": request.decision_reason,
            "execution_claimed_at": request.execution_claimed_at,
            "execution_claimed_by": request.execution_claimed_by,
            "execution_error": request.execution_error,
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
            payload_hash=(str(row["payload_hash"]) if row.get("payload_hash") else None),
            created_at=str(row.get("created_at") or ""),
            decided_at=(str(row["decided_at"]) if row.get("decided_at") else None),
            decided_by=(str(row["decided_by"]) if row.get("decided_by") else None),
            decision_reason=(str(row["decision_reason"]) if row.get("decision_reason") else None),
            execution_claimed_at=(
                str(row["execution_claimed_at"]) if row.get("execution_claimed_at") else None
            ),
            execution_claimed_by=(
                str(row["execution_claimed_by"]) if row.get("execution_claimed_by") else None
            ),
            execution_error=(str(row["execution_error"]) if row.get("execution_error") else None),
            executed_at=(str(row["executed_at"]) if row.get("executed_at") else None),
        )
