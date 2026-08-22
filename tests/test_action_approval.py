from jafar.action_approval import ActionState, LegalActionApprovalEngine


def test_legal_action_requires_explicit_approval():
    engine = LegalActionApprovalEngine()
    request = engine.propose(action_id="a1", action_type="send_email", description="Отправить проект ответа", evidence_ids=["e1"])
    assert request.state is ActionState.PROPOSED
    approval = engine.approve(request, "Артур")
    assert approval["state"] == "approved"
    assert approval["approved_by"] == "Артур"


def test_rejection_requires_reason():
    engine = LegalActionApprovalEngine()
    request = engine.propose(action_id="a2", action_type="telegram_publish", description="Опубликовать пост")
    rejected = engine.reject(request, "Артур", "Требует дополнительной проверки")
    assert rejected["state"] == "rejected"
