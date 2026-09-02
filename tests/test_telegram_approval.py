import json
import sqlite3

import pytest

from jafar.telegram_approval import TelegramApprovalStore


def test_telegram_publication_requires_explicit_approval(tmp_path):
    store = TelegramApprovalStore(tmp_path / "telegram.sqlite3")
    record = store.create(
        kind="post",
        chat_id="-100123",
        payload={"text": "Тест", "photo_url": None},
        scheduled_for=None,
        requested_by="chatgpt",
    )
    assert record.state == "proposed"
    approved = store.approve(record.approval_id, approver="owner")
    assert approved.state == "approved"
    assert approved.payload_hash == record.payload_hash


def test_telegram_approval_fails_closed_if_persisted_payload_changes(tmp_path):
    db = tmp_path / "telegram.sqlite3"
    store = TelegramApprovalStore(db)
    record = store.create(
        kind="post",
        chat_id="-100123",
        payload={"text": "Исходный текст"},
        scheduled_for=None,
        requested_by="chatgpt",
    )
    with sqlite3.connect(db) as con:
        con.execute(
            "UPDATE telegram_publication_approvals SET payload_json=? WHERE approval_id=?",
            (json.dumps({"text": "Изменённый текст"}), record.approval_id),
        )
    with pytest.raises(RuntimeError, match="payload_mismatch"):
        store.get(record.approval_id)


def test_execution_state_cannot_be_marked_without_approval(tmp_path):
    store = TelegramApprovalStore(tmp_path / "telegram.sqlite3")
    record = store.create(
        kind="post",
        chat_id="-100123",
        payload={"text": "Тест"},
        scheduled_for=None,
        requested_by="chatgpt",
    )
    with pytest.raises(RuntimeError, match="execution_state_mismatch"):
        store.mark_published(record.approval_id, message_id=123)


def test_uncertain_reconciliation_is_audited_and_does_not_rerun_handler(tmp_path):
    store = TelegramApprovalStore(tmp_path / "telegram.sqlite3")
    record = store.create(
        kind="post",
        chat_id="-100123",
        payload={"text": "Тест"},
        scheduled_for=None,
        requested_by="chatgpt",
    )
    store.approve(record.approval_id, approver="owner")
    store.mark_delivery_uncertain(record.approval_id)

    reconciled = store.reconcile_uncertain(
        record.approval_id,
        operator="owner",
        confirmed_executed=True,
        message_id=321,
        evidence_note="Публикация подтверждена вручную в Telegram.",
    )
    assert reconciled.state == "executed"
    assert reconciled.message_id == 321
    history = store.reconciliation_history(record.approval_id)
    assert len(history) == 1
    assert history[0]["confirmed_executed"] is True
    assert history[0]["message_id"] == 321


def test_uncertain_not_executed_can_return_to_same_approved_payload(tmp_path):
    store = TelegramApprovalStore(tmp_path / "telegram.sqlite3")
    record = store.create(
        kind="post",
        chat_id="-100123",
        payload={"text": "Тест"},
        scheduled_for=None,
        requested_by="chatgpt",
    )
    approved = store.approve(record.approval_id, approver="owner")
    store.mark_delivery_uncertain(record.approval_id)

    reconciled = store.reconcile_uncertain(
        record.approval_id,
        operator="owner",
        confirmed_executed=False,
        evidence_note="В истории канала и журнале бота публикация отсутствует.",
    )
    assert reconciled.state == "approved"
    assert reconciled.payload_hash == approved.payload_hash
