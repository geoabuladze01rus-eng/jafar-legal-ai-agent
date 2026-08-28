from jafar.action_approval import (
    ActionApprovalStore,
    ActionRequest,
    ActionState,
    LegalActionApprovalEngine,
)
from jafar.approval_execution import ApprovalExecutionService, ApprovalRequest


class LegacyUnboundApprovalStore:
    def __init__(self) -> None:
        self.request = ActionRequest(
            action_id="mail-unbound",
            action_type="send_email",
            description="Старый запрос без payload binding",
            state=ActionState.APPROVED,
            decided_at="2026-08-28T12:00:00+00:00",
            decided_by="lawyer",
        )

    def get(self, action_id: str) -> ActionRequest | None:
        return self.request if action_id == self.request.action_id else None


def test_legacy_side_effect_requires_explicit_approval():
    service = ApprovalExecutionService()
    service.register("send_email", lambda payload: {"sent_to": payload["to"]})
    request = ApprovalRequest("ap-1", "send_email", "Ответ клиенту", ("e1",))
    assert service.execute(request, {"to": "client@example.com"}, approved=False).status == "approval_required"
    assert service.execute(request, {"to": "client@example.com"}, approved=True).status == "executed"


def test_store_backed_execution_claims_then_marks_executed():
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    service = ApprovalExecutionService(store, executor_id="worker-1")
    service.register("send_email", lambda payload: {"sent_to": payload["to"]})
    payload = {"to": "client@example.com"}
    action = engine.propose(
        action_id="mail-1",
        action_type="send_email",
        description="Ответ клиенту",
        payload=payload,
    )
    engine.approve(action, "lawyer:chernov")

    executed = service.execute_approved("mail-1", payload)
    assert executed.status == "executed"
    saved = store.get("mail-1")
    assert saved is not None
    assert saved.state is ActionState.EXECUTED
    assert saved.execution_claimed_by == "worker-1"
    assert saved.executed_at is not None


def test_second_worker_cannot_duplicate_an_in_progress_external_action():
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    payload = {"to": "client@example.com"}
    action = engine.propose(
        action_id="mail-concurrent",
        action_type="send_email",
        description="Отправить один раз",
        payload=payload,
    )
    engine.approve(action, "lawyer")
    store.claim_for_execution("mail-concurrent", executor_id="worker-1")

    calls: list[dict] = []
    second = ApprovalExecutionService(store, executor_id="worker-2")
    second.register("send_email", lambda value: calls.append(value) or value)
    result = second.execute_approved("mail-concurrent", payload)

    assert result.status == "in_progress"
    assert calls == []
    assert store.get("mail-concurrent").execution_claimed_by == "worker-1"


def test_payload_cannot_change_after_lawyer_approval():
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    service = ApprovalExecutionService(store)
    calls: list[dict] = []
    service.register("send_email", lambda payload: calls.append(payload) or payload)
    approved_payload = {"to": "client@example.com", "subject": "Версия 1"}
    action = engine.propose(
        action_id="mail-bound",
        action_type="send_email",
        description="Отправить согласованное письмо",
        payload=approved_payload,
    )
    engine.approve(action, "lawyer")
    result = service.execute_approved(
        "mail-bound", {"to": "other@example.com", "subject": "Версия 1"}
    )
    assert result.status == "payload_mismatch"
    assert calls == []
    assert store.get("mail-bound").state is ActionState.APPROVED


def test_unbound_legacy_approval_fails_closed_in_store_backed_execution():
    store = LegacyUnboundApprovalStore()
    service = ApprovalExecutionService(store)
    calls: list[dict] = []
    service.register("send_email", lambda payload: calls.append(payload) or payload)
    result = service.execute_approved("mail-unbound", {"to": "client@example.com"})
    assert result.status == "payload_binding_required"
    assert calls == []


def test_rejected_action_can_never_execute():
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    service = ApprovalExecutionService(store)
    service.register("file_motion", lambda payload: payload)
    action = engine.propose(action_id="motion-1", action_type="file_motion", description="Подать")
    engine.reject(action, "lawyer", "Доработать правовую позицию")
    result = service.execute_approved("motion-1", {"document": "motion.docx"})
    assert result.status == "rejected"
    assert store.get("motion-1").state is ActionState.REJECTED


def test_handler_failure_releases_claim_but_preserves_approval_for_retry():
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    service = ApprovalExecutionService(store, executor_id="worker-1")

    def fail(_: dict) -> dict:
        raise RuntimeError("transport unavailable")

    service.register("send_email", fail)
    payload = {"to": "client@example.com"}
    action = engine.propose(
        action_id="mail-fail",
        action_type="send_email",
        description="Отправить письмо",
        payload=payload,
    )
    engine.approve(action, "lawyer")
    result = service.execute_approved("mail-fail", payload)

    saved = store.get("mail-fail")
    assert result.status == "error"
    assert saved.state is ActionState.APPROVED
    assert saved.execution_claimed_by is None
    assert saved.execution_error == "transport unavailable"
    assert saved.executed_at is None


def test_post_side_effect_persistence_failure_never_releases_claim_for_automatic_retry():
    class MarkFailStore(ActionApprovalStore):
        def mark_executed(self, action_id: str, *, executor_id: str | None = None):
            raise RuntimeError("database unavailable")

    store = MarkFailStore()
    engine = LegalActionApprovalEngine(store)
    service = ApprovalExecutionService(store, executor_id="worker-1")
    calls: list[dict] = []
    service.register("send_email", lambda payload: calls.append(payload) or payload)
    payload = {"to": "client@example.com"}
    action = engine.propose(
        action_id="mail-uncertain",
        action_type="send_email",
        description="Отправить письмо",
        payload=payload,
    )
    engine.approve(action, "lawyer")

    result = service.execute_approved("mail-uncertain", payload)
    saved = store.get("mail-uncertain")

    assert result.status == "execution_recovery_required"
    assert calls == [payload]
    assert saved.state is ActionState.EXECUTING
    assert saved.execution_claimed_by == "worker-1"
