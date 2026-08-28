from datetime import datetime, timedelta, timezone

import pytest

from jafar.action_approval import ActionApprovalStore, ActionState, LegalActionApprovalEngine
from jafar.action_reconciliation import ActionReconciliationService, ReconciliationDecision


def _executing_store() -> ActionApprovalStore:
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    action = engine.propose(
        action_id="mail-1",
        action_type="send_email",
        description="Отправить согласованное письмо",
        payload={"to": "client@example.com", "subject": "Ответ"},
    )
    engine.approve(action, "lawyer:test")
    store.claim_for_execution("mail-1", executor_id="worker:1")
    return store


def test_stale_executing_action_becomes_reconciliation_candidate() -> None:
    store = _executing_store()
    action = store.get("mail-1")
    assert action is not None and action.execution_claimed_at
    claimed = datetime.fromisoformat(action.execution_claimed_at)

    service = ActionReconciliationService(store, stale_after=timedelta(minutes=10))
    candidates = service.candidates(now=claimed + timedelta(minutes=11))

    assert len(candidates) == 1
    assert candidates[0].action_id == "mail-1"
    assert candidates[0].claimed_by == "worker:1"
    assert candidates[0].age_seconds >= 660


def test_fresh_execution_claim_is_not_auto_recovery_candidate() -> None:
    store = _executing_store()
    action = store.get("mail-1")
    claimed = datetime.fromisoformat(action.execution_claimed_at)
    service = ActionReconciliationService(store, stale_after=timedelta(minutes=10))

    assert service.candidates(now=claimed + timedelta(minutes=5)) == ()
    assert store.get("mail-1").state is ActionState.EXECUTING


def test_confirmed_not_executed_releases_claim_only_with_evidence_note() -> None:
    store = _executing_store()
    service = ActionReconciliationService(store)

    with pytest.raises(ValueError, match="reconciliation_evidence_note_required"):
        service.reconcile(
            "mail-1",
            decision=ReconciliationDecision.CONFIRMED_NOT_EXECUTED,
            operator_id="ops:1",
            evidence_note="",
        )

    recovered = service.reconcile(
        "mail-1",
        decision=ReconciliationDecision.CONFIRMED_NOT_EXECUTED,
        operator_id="ops:1",
        evidence_note="SMTP provider confirms no message accepted",
    )

    assert recovered.state is ActionState.APPROVED
    assert recovered.execution_claimed_by is None
    assert "ops:1" in (recovered.execution_error or "")
    audit = service.audit_for_action("mail-1")
    assert len(audit) == 1
    assert audit[0].decision is ReconciliationDecision.CONFIRMED_NOT_EXECUTED
    assert audit[0].operator_id == "ops:1"
    assert "SMTP provider" in audit[0].evidence_note


def test_confirmed_executed_marks_existing_claim_without_second_handler_call() -> None:
    store = _executing_store()
    service = ActionReconciliationService(store)

    reconciled = service.reconcile(
        "mail-1",
        decision=ReconciliationDecision.CONFIRMED_EXECUTED,
        operator_id="ops:1",
        evidence_note="Provider delivery log confirms accepted message id 123",
    )

    assert reconciled.state is ActionState.EXECUTED
    assert reconciled.executed_at is not None
    assert reconciled.execution_claimed_by == "worker:1"
    audit = service.audit_for_action("mail-1")
    assert len(audit) == 1
    assert audit[0].decision is ReconciliationDecision.CONFIRMED_EXECUTED
    assert audit[0].operator_id == "ops:1"
    assert "message id 123" in audit[0].evidence_note


def test_failed_reconciliation_does_not_append_audit_record() -> None:
    store = _executing_store()
    service = ActionReconciliationService(store)

    with pytest.raises(ValueError, match="operator_id_required"):
        service.reconcile(
            "mail-1",
            decision=ReconciliationDecision.CONFIRMED_EXECUTED,
            operator_id="",
            evidence_note="provider confirms delivery",
        )

    assert service.audit_for_action("mail-1") == ()


def test_reconciliation_refuses_non_executing_action() -> None:
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    action = engine.propose(
        action_id="pending",
        action_type="send_email",
        description="Pending",
        payload={"to": "client@example.com"},
    )
    engine.approve(action, "lawyer:test")
    service = ActionReconciliationService(store)

    with pytest.raises(ValueError, match="action_not_executing"):
        service.reconcile(
            "pending",
            decision=ReconciliationDecision.CONFIRMED_NOT_EXECUTED,
            operator_id="ops:1",
            evidence_note="checked",
        )


def test_candidates_require_timezone_aware_clock() -> None:
    store = _executing_store()
    service = ActionReconciliationService(store)

    with pytest.raises(ValueError, match="now_must_be_timezone_aware"):
        service.candidates(now=datetime(2026, 8, 28, 12, 0, 0))
