from __future__ import annotations

import hashlib
import hmac
import sqlite3

from jafar.telegram_polls import TelegramPollStore


def _sent(store: TelegramPollStore, poll_id: str = "poll-1") -> None:
    store.record_sent(
        poll={"id": poll_id, "question": "Q", "options": []},
        chat_id="-1001",
        message_id=1,
    )


def test_unknown_aggregate_poll_update_is_rejected(tmp_path) -> None:
    store = TelegramPollStore(
        tmp_path / "telegram.sqlite3",
        identity_secret="poll-identity-secret-that-is-long-enough",
    )

    accepted = store.ingest_update(
        {
            "poll": {
                "id": "foreign-poll",
                "question": "Foreign",
                "options": [{"text": "A", "voter_count": 1}],
                "total_voter_count": 1,
            }
        }
    )

    assert accepted is False
    try:
        store.results("foreign-poll")
    except KeyError:
        pass
    else:
        raise AssertionError("foreign poll must not be inserted into Jafar poll state")


def test_unknown_poll_answer_is_rejected_even_without_identity_secret(tmp_path) -> None:
    store = TelegramPollStore(tmp_path / "telegram.sqlite3")

    assert not store.ingest_update(
        {"poll_answer": {"poll_id": "unknown", "user": {"id": 7}, "option_ids": [0]}}
    )


def test_known_poll_answer_without_secret_is_consumed_but_identity_is_not_stored(tmp_path) -> None:
    store = TelegramPollStore(tmp_path / "telegram.sqlite3")
    _sent(store)

    assert store.ingest_update(
        {"poll_answer": {"poll_id": "poll-1", "user": {"id": 7}, "option_ids": [0]}}
    )
    assert store.results("poll-1")["answers"] == []


def test_known_poll_answer_is_hmac_pseudonymized(tmp_path) -> None:
    secret = "poll-identity-secret-that-is-long-enough"
    store = TelegramPollStore(tmp_path / "telegram.sqlite3", identity_secret=secret)
    _sent(store)

    assert store.ingest_update(
        {"poll_answer": {"poll_id": "poll-1", "user": {"id": 7}, "option_ids": [0]}}
    )

    expected = hmac.new(secret.encode(), b"user:7", hashlib.sha256).hexdigest()
    assert store.results("poll-1")["answers"] == [
        {"voter_key": expected, "option_ids": [0]}
    ]


def test_legacy_numeric_voter_id_migrates_to_new_user_namespace(tmp_path) -> None:
    path = tmp_path / "telegram.sqlite3"
    bootstrap = TelegramPollStore(path)
    _sent(bootstrap)
    with sqlite3.connect(path) as con:
        con.execute(
            "INSERT INTO telegram_poll_answers VALUES (?, ?, ?, ?)",
            ("poll-1", "7", "[0]", "2026-08-29T00:00:00+00:00"),
        )

    secret = "poll-identity-secret-that-is-long-enough"
    migrated = TelegramPollStore(path, identity_secret=secret)
    expected = hmac.new(secret.encode(), b"user:7", hashlib.sha256).hexdigest()

    assert migrated.results("poll-1")["answers"] == [
        {"voter_key": expected, "option_ids": [0]}
    ]
