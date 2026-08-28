import pytest

from jafar.action_approval import (
    ActionApprovalStore,
    ActionState,
    LegalActionApprovalEngine,
)


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


def test_rejection_requires_reason():
    engine = LegalActionApprovalEngine()
    request = engine.propose(
        action_id="a2",
        action_type="telegram_publish",
        description="Опубликовать пост",
    )
    rejected = engine.reject(request, "Артур", "Требует дополнительной проверки")
    assert rejected["state"] == "rejected"


def test_pending_store_tracks_proposals_until_explicit_decision() -> None:
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    request = engine.propose(
        action_id="a3",
        action_type="send_email",
        description="Отправить юридически значимое письмо",
    )

    assert store.pending() == (request,)

    engine.approve(request, "lawyer:chernov")

    assert store.pending() == ()


def test_pending_store_rejects_duplicate_action_ids() -> None:
    store = ActionApprovalStore()
    engine = LegalActionApprovalEngine(store)
    engine.propose(
        action_id="duplicate",
        action_type="send_email",
        description="Первый запрос",
    )

    with pytest.raises(ValueError, match="duplicate_action_id"):
        engine.propose(
            action_id="duplicate",
            action_type="send_email",
            description="Второй запрос",
        )
