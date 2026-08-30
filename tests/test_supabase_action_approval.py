from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest

from jafar.action_approval import (
    ActionRequest,
    ActionState,
    LegalActionApprovalEngine,
    payload_fingerprint,
)
from jafar.supabase_action_approval import SupabaseActionApprovalRepository


class FakeQuery:
    def __init__(self, client: FakeSupabase, table: str) -> None:
        self.client = client
        self.table_name = table
        self.filters: list[tuple[str, Any]] = []
        self.single = False
        self.insert_payload: Any = None
        self.update_payload: dict[str, Any] | None = None

    def select(self, _: str) -> FakeQuery:
        return self

    def eq(self, field: str, value: Any) -> FakeQuery:
        self.filters.append((field, value))
        return self

    def maybe_single(self) -> FakeQuery:
        self.single = True
        return self

    def order(self, _: str) -> FakeQuery:
        return self

    def insert(self, payload: Any) -> FakeQuery:
        self.insert_payload = deepcopy(payload)
        return self

    def update(self, payload: dict[str, Any]) -> FakeQuery:
        self.update_payload = deepcopy(payload)
        return self

    def execute(self) -> SimpleNamespace:
        rows = self.client.data.setdefault(self.table_name, [])
        if self.insert_payload is not None:
            inserted = deepcopy(
                self.insert_payload if isinstance(self.insert_payload, list) else [self.insert_payload]
            )
            rows.extend(inserted)
            return SimpleNamespace(data=deepcopy(inserted))

        indexes = [
            index
            for index, row in enumerate(rows)
            if all(row.get(field) == value for field, value in self.filters)
        ]
        if self.update_payload is not None:
            updated: list[dict[str, Any]] = []
            for index in indexes:
                rows[index].update(deepcopy(self.update_payload))
                updated.append(deepcopy(rows[index]))
            return SimpleNamespace(data=updated)

        selected = [deepcopy(rows[index]) for index in indexes] if self.filters else deepcopy(rows)
        if self.single:
            return SimpleNamespace(data=selected[0] if selected else None)
        return SimpleNamespace(data=selected)


class FakeSupabase:
    def __init__(self) -> None:
        self.data: dict[str, list[dict[str, Any]]] = {"action_approvals": []}

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self, name)


def make_request(action_id: str = "a1", *, bound: bool = True) -> ActionRequest:
    payload = {"to": "client@example.com", "subject": "Ответ"}
    return ActionRequest(
        action_id=action_id,
        action_type="send_email",
        description="Отправить письмо доверителю",
        evidence_ids=("e1", "e2"),
        payload_hash=payload_fingerprint(payload) if bound else None,
        created_at="2026-08-28T12:00:00+00:00",
    )


def test_supabase_store_retains_full_claim_and_execution_history() -> None:
    client = FakeSupabase()
    store = SupabaseActionApprovalRepository(client, "owner-1")
    engine = LegalActionApprovalEngine(store)
    request = make_request()
    store.add(request)
    engine.approve(request, "lawyer:chernov")

    claimed = store.claim_for_execution(request.action_id, executor_id="worker-1")
    executed = store.mark_executed(request.action_id, executor_id="worker-1")

    assert claimed.state is ActionState.EXECUTING
    assert executed.state is ActionState.EXECUTED
    assert executed.execution_claimed_by == "worker-1"
    assert executed.execution_claimed_at is not None
    assert executed.executed_at is not None
    assert executed.payload_hash == request.payload_hash
    assert store.executing() == ()
    assert store.executed()[0].evidence_ids == ("e1", "e2")


def test_second_executor_cannot_claim_same_action() -> None:
    client = FakeSupabase()
    store = SupabaseActionApprovalRepository(client, "owner-1")
    request = make_request("claim-once")
    store.add(request)
    store.decide("claim-once", state=ActionState.APPROVED, decided_by="lawyer")

    first = store.claim_for_execution("claim-once", executor_id="worker-1")
    with pytest.raises(ValueError, match="action_not_available_for_execution"):
        store.claim_for_execution("claim-once", executor_id="worker-2")

    assert first.execution_claimed_by == "worker-1"
    assert store.get("claim-once").execution_claimed_by == "worker-1"


def test_claim_release_requires_owner_and_preserves_retry_error() -> None:
    client = FakeSupabase()
    store = SupabaseActionApprovalRepository(client, "owner-1")
    request = make_request("retry")
    store.add(request)
    store.decide("retry", state=ActionState.APPROVED, decided_by="lawyer")
    store.claim_for_execution("retry", executor_id="worker-1")

    with pytest.raises(ValueError, match="execution_claim_owner_mismatch"):
        store.release_execution_claim("retry", executor_id="worker-2", error="timeout")

    released = store.release_execution_claim("retry", executor_id="worker-1", error="timeout")
    assert released.state is ActionState.APPROVED
    assert released.execution_claimed_by is None
    assert released.execution_error == "timeout"


def test_payload_hash_is_persisted_and_hydrated() -> None:
    client = FakeSupabase()
    store = SupabaseActionApprovalRepository(client, "owner-1")
    request = make_request("payload-bound")
    store.add(request)
    hydrated = store.get("payload-bound")
    assert hydrated is not None
    assert hydrated.payload_hash == request.payload_hash


def test_unbound_action_cannot_transition_to_approved() -> None:
    client = FakeSupabase()
    store = SupabaseActionApprovalRepository(client, "owner-1")
    request = make_request("unbound", bound=False)
    store.add(request)
    with pytest.raises(ValueError, match="payload_binding_required"):
        store.decide("unbound", state=ActionState.APPROVED, decided_by="lawyer")
    assert store.get("unbound").state is ActionState.PROPOSED


def test_second_decision_cannot_overwrite_first_lawyer_decision() -> None:
    client = FakeSupabase()
    store = SupabaseActionApprovalRepository(client, "owner-1")
    store.add(make_request())
    approved = store.decide("a1", state=ActionState.APPROVED, decided_by="lawyer:first")

    with pytest.raises(ValueError, match="action_not_pending"):
        store.decide(
            "a1",
            state=ActionState.REJECTED,
            decided_by="lawyer:second",
            reason="Позднее",
        )
    assert store.get("a1") == approved


def test_rejection_requires_reason_and_remains_queryable() -> None:
    client = FakeSupabase()
    store = SupabaseActionApprovalRepository(client, "owner-1")
    store.add(make_request("reject-1"))
    with pytest.raises(ValueError, match="rejection_reason_required"):
        store.decide("reject-1", state=ActionState.REJECTED, decided_by="lawyer")
    rejected = store.decide(
        "reject-1",
        state=ActionState.REJECTED,
        decided_by="lawyer",
        reason="Проверить",
    )
    assert store.rejected() == (rejected,)


def test_store_is_strictly_owner_scoped() -> None:
    client = FakeSupabase()
    owner_one = SupabaseActionApprovalRepository(client, "owner-1")
    owner_two = SupabaseActionApprovalRepository(client, "owner-2")
    owner_one.add(make_request("same-id"))
    owner_two.add(make_request("same-id"))
    owner_one.decide("same-id", state=ActionState.APPROVED, decided_by="lawyer:one")
    assert owner_one.get("same-id").state is ActionState.APPROVED
    assert owner_two.get("same-id").state is ActionState.PROPOSED


def test_duplicate_action_id_is_rejected_within_owner() -> None:
    client = FakeSupabase()
    store = SupabaseActionApprovalRepository(client, "owner-1")
    store.add(make_request("duplicate"))
    with pytest.raises(ValueError, match="duplicate_action_id"):
        store.add(make_request("duplicate"))


def test_pending_action_cannot_be_claimed_or_executed() -> None:
    client = FakeSupabase()
    store = SupabaseActionApprovalRepository(client, "owner-1")
    store.add(make_request("pending"))
    with pytest.raises(ValueError, match="action_not_available_for_execution"):
        store.claim_for_execution("pending", executor_id="worker")
    with pytest.raises(ValueError, match="only_executing_action_can_be_executed"):
        store.mark_executed("pending", executor_id="worker")
