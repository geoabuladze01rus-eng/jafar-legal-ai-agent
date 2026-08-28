import pytest

from jafar.action_approval import (
    ActionApprovalStore,
    ActionState,
    LegalActionApprovalEngine,
    payload_fingerprint,
)


def test_payload_fingerprint_is_stable_for_key_order_and_sensitive_to_changes() -> None:
    first = payload_fingerprint({"subject": "Ответ", "to": "client@example.com"})
    reordered = payload_fingerprint({"to": "client@example.com", "subject": "Ответ"})
    changed = payload_fingerprint({"to": "other@example.com", "subject": "Ответ"})
    assert first == reordered
    assert first != changed


def test_payload_fingerprint_rejects_non_finite_json_values() -> None:
    with pytest.raises(ValueError):
        payload_fingerprint({"confidence": float("nan")})


def test_legal_action_requires_explicit_payload_bound_approval():
    engine = LegalActionApprovalEngine()
    request = engine.propose(
        action_id="a1",
        action_type="send_email",
        description="Отправить проект ответа",
        evidence_ids=["e1"],
        payload={"to": "client@example.com", "subject": "Проект ответа"},
    )
    assert request.state is ActionState.PROPOSED
    approval = engine.approve(request, "Артур")
    assert approval["state"] == "approved"
    assert approval["approved_by"] == "Артур"
    assert approval["decided_at"]


def test_unbound_action_cannot_be_approved():
    engine = LegalActionApprovalEngine()
    request = engine.propose(action_id="unbound", action_type="send_email", description="Запрос")
    with pytest.raises(ValueError, match="payload_binding_required"):
        engine.approve(request, "Артур")


def test_rejection_requires_reason():
    engine = LegalActionApprovalEngine()
    request = engine.propose(action_id="a2", action_type="telegram_publish", description="Пост")
    rejected = engine.reject(request, "Артур", "Требует дополнительной проверки")
    assert rejected["state"] == "rejected"
    assert rejected["reason"] == "Требует дополнительной проверки"


def test_store_retains_approved_action_for_separate_claimed_execution() -> None:
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    request = engine.propose(
        action_id="a3",
        action_type="send_email",
        description="Отправить юридически значимое письмо",
        payload={"to": "client@example.com", "subject": "Согласованный ответ"},
    )
    engine.approve(request, "lawyer:chernov")

    approved = store.approved()[0]
    assert approved.payload_hash == request.payload_hash

    claimed = store.claim_for_execution("a3", executor_id="worker-1")
    assert claimed.state is ActionState.EXECUTING
    assert claimed.execution_claimed_by == "worker-1"
    assert claimed.execution_claimed_at is not None

    with pytest.raises(ValueError, match="action_not_available_for_execution"):
        store.claim_for_execution("a3", executor_id="worker-2")

    executed = store.mark_executed("a3", executor_id="worker-1")
    assert executed.state is ActionState.EXECUTED
    assert executed.executed_at is not None
    assert store.executing() == ()
    assert store.executed() == (executed,)


def test_failed_execution_claim_can_be_released_for_controlled_retry() -> None:
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    action = engine.propose(
        action_id="retry",
        action_type="send_email",
        description="Отправить письмо",
        payload={"to": "client@example.com"},
    )
    engine.approve(action, "lawyer")
    store.claim_for_execution("retry", executor_id="worker-1")

    with pytest.raises(ValueError, match="execution_claim_owner_mismatch"):
        store.release_execution_claim("retry", executor_id="worker-2", error="timeout")

    released = store.release_execution_claim(
        "retry", executor_id="worker-1", error="transport unavailable"
    )
    assert released.state is ActionState.APPROVED
    assert released.execution_claimed_by is None
    assert released.execution_claimed_at is None
    assert released.execution_error == "transport unavailable"


def test_rejected_action_remains_auditable() -> None:
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    request = engine.propose(action_id="reject-me", action_type="file_motion", description="Подать")
    engine.reject(request, "lawyer:chernov", "Не готово к подаче")
    rejected = store.rejected()[0]
    assert rejected.state is ActionState.REJECTED
    assert rejected.decision_reason == "Не готово к подаче"


def test_store_rejects_duplicate_action_ids_even_after_decision() -> None:
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    request = engine.propose(
        action_id="duplicate",
        action_type="send_email",
        description="Первый запрос",
        payload={"to": "client@example.com"},
    )
    engine.approve(request, "lawyer")
    with pytest.raises(ValueError, match="duplicate_action_id"):
        engine.propose(
            action_id="duplicate",
            action_type="send_email",
            description="Второй запрос",
            payload={"to": "other@example.com"},
        )


def test_only_executing_action_can_be_marked_executed() -> None:
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    engine.propose(
        action_id="still-pending",
        action_type="send_email",
        description="Не выполнять без решения",
        payload={"to": "client@example.com"},
    )
    with pytest.raises(ValueError, match="only_executing_action_can_be_executed"):
        store.mark_executed("still-pending")
