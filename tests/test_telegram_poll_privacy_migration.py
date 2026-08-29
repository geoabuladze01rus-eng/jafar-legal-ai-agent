from __future__ import annotations

import hashlib
import hmac
import sqlite3

from jafar.config import settings
from jafar.telegram_polls import TelegramPollStore
from jafar.telegram_runtime import TelegramRuntime


def _digest(secret: str, identity: str) -> str:
    return hmac.new(secret.encode(), identity.encode(), hashlib.sha256).hexdigest()


def test_legacy_user_id_migrates_to_current_user_namespace(tmp_path) -> None:
    path = tmp_path / "polls.sqlite3"
    store = TelegramPollStore(path)
    store.record_sent(
        poll={"id": "poll-1", "question": "Q", "options": []},
        chat_id="-1001",
        message_id=1,
    )
    with sqlite3.connect(path) as con:
        con.execute(
            "INSERT INTO telegram_poll_answers VALUES (?, ?, ?, ?)",
            ("poll-1", "7", "[0]", "2026-08-29T00:00:00+00:00"),
        )

    secret = "poll-identity-secret-that-is-long-enough"
    migrated = TelegramPollStore(path, identity_secret=secret)
    expected = _digest(secret, "user:7")
    assert migrated.results("poll-1")["answers"] == [
        {"voter_key": expected, "option_ids": [0]}
    ]

    assert migrated.ingest_update(
        {"poll_answer": {"poll_id": "poll-1", "user": {"id": 7}, "option_ids": [1]}}
    )
    assert migrated.results("poll-1")["answers"] == [
        {"voter_key": expected, "option_ids": [1]}
    ]


def test_legacy_voter_chat_namespace_is_preserved(tmp_path) -> None:
    path = tmp_path / "polls.sqlite3"
    store = TelegramPollStore(path)
    store.record_sent(
        poll={"id": "poll-1", "question": "Q", "options": []},
        chat_id="-1001",
        message_id=1,
    )
    with sqlite3.connect(path) as con:
        con.execute(
            "INSERT INTO telegram_poll_answers VALUES (?, ?, ?, ?)",
            ("poll-1", "chat:-2002", "[0]", "2026-08-29T00:00:00+00:00"),
        )

    secret = "poll-identity-secret-that-is-long-enough"
    migrated = TelegramPollStore(path, identity_secret=secret)
    assert migrated.results("poll-1")["answers"][0]["voter_key"] == _digest(
        secret, "chat:-2002"
    )


def test_runtime_uses_configured_poll_identity_secret(monkeypatch, tmp_path) -> None:
    secret = "poll-identity-secret-that-is-long-enough"
    monkeypatch.setattr(settings, "telegram_scheduler_db_path", str(tmp_path / "polls.sqlite3"))
    monkeypatch.setattr(settings, "telegram_poll_identity_secret", secret)
    runtime = TelegramRuntime("123456:abcdefghijklmnopqrstuvwxyz")
    runtime.poll_store.record_sent(
        poll={"id": "poll-1", "question": "Q", "options": []},
        chat_id="-1001",
        message_id=1,
    )

    import asyncio

    asyncio.run(
        runtime.handle_update(
            {"poll_answer": {"poll_id": "poll-1", "user": {"id": 7}, "option_ids": [0]}}
        )
    )
    assert runtime.poll_store.results("poll-1")["answers"][0]["voter_key"] == _digest(
        secret, "user:7"
    )
