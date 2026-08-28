from jafar.action_approval import ActionApprovalStore, ActionState, LegalActionApprovalEngine
from jafar.approval_execution import ApprovalExecutionService, ApprovalRequest


def test_legacy_side_effect_requires_explicit_approval():
    service = ApprovalExecutionService()
    service.register("send_email", lambda payload: {"sent_to": payload["to"]})
    request = ApprovalRequest("ap-1", "send_email", "Ответ клиенту", ("e1",))

    pending = service.execute(request, {"to": "client@example.com"}, approved=False)
    assert pending.status == "approval_required"

    result = service.execute(request, {"to": "client@example.com"}, approved=True)
    assert result.status == "executed"
    assert result.data == {"sent_to": "client@example.com"}


def test_store_backed_execution_ignores_caller_boolean_until_lawyer_approves():
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    service = ApprovalExecutionService(store)
    service.register("send_email", lambda payload: {"sent_to": payload["to"]})
    payload = {"to": "client@example.com"}
    action = engine.propose(
        action_id="mail-1",
        action_type="send_email",
        description="Ответ клиенту",
        payload=payload,
    )
    legacy_request = ApprovalRequest("mail-1", "send_email", "Ответ клиенту")

    bypass_attempt = service.execute(
        legacy_request,
        payload,
        approved=True,
    )

    assert bypass_attempt.status == "approval_required"
    assert store.get("mail-1").state is ActionState.PROPOSED

    engine.approve(action, "lawyer:chernov")
    executed = service.execute_approved("mail-1", payload)

    assert executed.status == "executed"
    assert executed.data == {"sent_to": "client@example.com"}
    assert store.get("mail-1").state is ActionState.EXECUTED
    assert store.get("mail-1").executed_at is not None


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
        "mail-bound",
        {"to": "other@example.com", "subject": "Версия 1"},
    )

    assert result.status == "payload_mismatch"
    assert calls == []
    assert store.get("mail-bound").state is ActionState.APPROVED


def test_unbound_legacy_approval_fails_closed_in_store_backed_execution():
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    service = ApprovalExecutionService(store)
    calls: list[dict] = []
    service.register("send_email", lambda payload: calls.append(payload) or payload)
    action = engine.propose(
        action_id="mail-unbound",
        action_type="send_email",
        description="Старый запрос без payload binding",
    )
    engine.approve(action, "lawyer")

    result = service.execute_approved("mail-unbound", {"to": "client@example.com"})

    assert result.status == "payload_binding_required"
    assert calls == []
    assert store.get("mail-unbound").state is ActionState.APPROVED


def test_rejected_action_can_never_execute():
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    service = ApprovalExecutionService(store)
    service.register("file_motion", lambda payload: payload)
    action = engine.propose(
        action_id="motion-1",
        action_type="file_motion",
        description="Подать ходатайство",
    )
    engine.reject(action, "lawyer", "Доработать правовую позицию")

    result = service.execute_approved("motion-1", {"document": "motion.docx"})

    assert result.status == "rejected"
    assert store.get("motion-1").state is ActionState.REJECTED


def test_handler_failure_keeps_action_approved_for_review_or_retry():
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    service = ApprovalExecutionService(store)

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

    assert result.status == "error"
    assert store.get("mail-fail").state is ActionState.APPROVED
    assert store.get("mail-fail").executed_at is None
