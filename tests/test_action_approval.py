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


def test_legal_action_requires_explicit_approval():
    engine = LegalActionApprovalEngine()
    request = engine.propose(
        action_id="a1",
        action_type="send_email",
        description="Отправить проект ответа",
        evidence_ids=["e1"],
    )
    assert request.state is ActionState.PROPOSED
    approval = engine.approve(request, "Артур")
    assert approval["state"] == "approved"
    assert approval["approved_by"] == "Артур"
    assert approval["decided_at"]


def test_rejection_requires_reason():
    engine = LegalActionApprovalEngine()
    request = engine.propose(
        action_id="a2",
        action_type="telegram_publish",
        description="Опубликовать пост",
    )
    rejected = engine.reject(request, "Артур", "Требует дополнительной проверки")
    assert rejected["state"] == "rejected"
    assert rejected["reason"] == "Требует дополнительной проверки"


def test_store_retains_approved_action_for_separate_execution() -> None:
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    request = engine.propose(
        action_id="a3",
        action_type="send_email",
        description="Отправить юридически значимое письмо",
        payload={"to": "client@example.com", "subject": "Согласованный ответ"},
    )

    assert store.pending() == (request,)
    assert request.payload_hash

    engine.approve(request, "lawyer:chernov")

    assert store.pending() == ()
    assert len(store.approved()) == 1
    approved = store.approved()[0]
    assert approved.action_id == "a3"
    assert approved.decided_by == "lawyer:chernov"
    assert approved.decided_at is not None
    assert approved.payload_hash == request.payload_hash

    executed = store.mark_executed("a3")

    assert executed.state is ActionState.EXECUTED
    assert executed.executed_at is not None
    assert store.approved() == ()
    assert store.executed() == (executed,)


def test_rejected_action_remains_auditable() -> None:
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    request = engine.propose(
        action_id="reject-me",
        action_type="file_motion",
        description="Подать ходатайство",
    )

    engine.reject(request, "lawyer:chernov", "Не готово к подаче")

    rejected = store.rejected()[0]
    assert rejected.state is ActionState.REJECTED
    assert rejected.decision_reason == "Не готово к подаче"
    assert store.get("reject-me") == rejected


def test_store_rejects_duplicate_action_ids_even_after_decision() -> None:
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    request = engine.propose(
        action_id="duplicate",
        action_type="send_email",
        description="Первый запрос",
    )
    engine.approve(request, "lawyer")

    with pytest.raises(ValueError, match="duplicate_action_id"):
        engine.propose(
            action_id="duplicate",
            action_type="send_email",
            description="Второй запрос",
        )


def test_only_approved_action_can_be_marked_executed() -> None:
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    engine.propose(
        action_id="still-pending",
        action_type="send_email",
        description="Не выполнять без решения",
    )

    with pytest.raises(ValueError, match="only_approved_action_can_be_executed"):
        store.mark_executed("still-pending")


def test_approved_but_unbound_action_cannot_be_marked_executed() -> None:
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    request = engine.propose(
        action_id="approved-unbound",
        action_type="send_email",
        description="Старый запрос без зафиксированного payload",
    )
    engine.approve(request, "lawyer")

    with pytest.raises(ValueError, match="payload_binding_required"):
        store.mark_executed("approved-unbound")
