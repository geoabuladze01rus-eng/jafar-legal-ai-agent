from types import SimpleNamespace

from jafar.action_approval import ActionRequest, ActionState
from jafar.action_reconciliation import ReconciliationAuditStore, ReconciliationDecision
from jafar.supabase_action_reconciliation import SupabaseActionReconciliationService


class FakeRPC:
    def __init__(self, client, function: str, params: dict) -> None:
        self.client = client
        self.function = function
        self.params = params

    def execute(self):
        self.client.calls.append((self.function, self.params))
        self.client.repository.current = ActionRequest(
            action_id=self.params["p_action_id"],
            action_type="send_email",
            description="Send approved email",
            state=(
                ActionState.EXECUTED
                if self.params["p_decision"] == "confirmed_executed"
                else ActionState.APPROVED
            ),
            payload_hash="abc",
            created_at="2026-08-28T12:00:00+00:00",
            decided_at="2026-08-28T12:01:00+00:00",
            decided_by="lawyer:test",
            execution_claimed_at=(
                "2026-08-28T12:02:00+00:00"
                if self.params["p_decision"] == "confirmed_executed"
                else None
            ),
            execution_claimed_by=(
                "worker:1"
                if self.params["p_decision"] == "confirmed_executed"
                else None
            ),
            executed_at=(
                "2026-08-28T12:03:00+00:00"
                if self.params["p_decision"] == "confirmed_executed"
                else None
            ),
        )
        return SimpleNamespace(data={"action_id": self.params["p_action_id"]})


class FakeClient:
    def __init__(self, repository) -> None:
        self.repository = repository
        self.calls = []

    def rpc(self, function: str, params: dict):
        return FakeRPC(self, function, params)


class FakeApprovalRepository:
    def __init__(self) -> None:
        self.current = ActionRequest(
            action_id="mail-1",
            action_type="send_email",
            description="Send approved email",
            state=ActionState.EXECUTING,
            payload_hash="abc",
            created_at="2026-08-28T12:00:00+00:00",
            decided_at="2026-08-28T12:01:00+00:00",
            decided_by="lawyer:test",
            execution_claimed_at="2026-08-28T12:02:00+00:00",
            execution_claimed_by="worker:1",
        )

    def get(self, action_id: str):
        return self.current if action_id == self.current.action_id else None

    def executing(self):
        return (self.current,) if self.current.state is ActionState.EXECUTING else ()


def test_supabase_reconciliation_uses_single_atomic_rpc() -> None:
    repository = FakeApprovalRepository()
    client = FakeClient(repository)
    service = SupabaseActionReconciliationService(
        repository,
        ReconciliationAuditStore(),
        client=client,
        owner_user_id="owner-123",
    )

    result = service.reconcile(
        "mail-1",
        decision=ReconciliationDecision.CONFIRMED_EXECUTED,
        operator_id="ops:1",
        evidence_note="provider confirms delivery",
    )

    assert result.state is ActionState.EXECUTED
    assert len(client.calls) == 1
    function, params = client.calls[0]
    assert function == "reconcile_action_for_owner"
    assert params == {
        "p_owner_user_id": "owner-123",
        "p_action_id": "mail-1",
        "p_decision": "confirmed_executed",
        "p_operator_id": "ops:1",
        "p_evidence_note": "provider confirms delivery",
    }


def test_supabase_reconciliation_rejects_missing_evidence_before_rpc() -> None:
    repository = FakeApprovalRepository()
    client = FakeClient(repository)
    service = SupabaseActionReconciliationService(
        repository,
        ReconciliationAuditStore(),
        client=client,
        owner_user_id="owner-123",
    )

    try:
        service.reconcile(
            "mail-1",
            decision=ReconciliationDecision.CONFIRMED_NOT_EXECUTED,
            operator_id="ops:1",
            evidence_note="",
        )
    except ValueError as exc:
        assert str(exc) == "reconciliation_evidence_note_required"
    else:
        raise AssertionError("missing evidence note must fail")

    assert client.calls == []
