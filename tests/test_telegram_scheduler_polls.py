from __future__ import annotations

import asyncio
import os
import stat
from datetime import timedelta

import pytest

from jafar.telegram_polls import TelegramPollStore, validate_poll
from jafar.telegram_publishing import (
    TelegramPublisher,
    split_telegram_text,
    validate_filename,
    validate_photo_bytes,
    validate_photo_url,
)
from jafar.telegram_scheduler import TelegramScheduler, TelegramScheduleStore, utc_now


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.photos: list[dict] = []

    async def send_message(self, *, chat_id: str, text: str) -> dict:
        self.messages.append(text)
        return {"message_id": len(self.messages)}

    async def send_photo(self, **kwargs: object) -> dict:
        self.photos.append(kwargs)
        return {"message_id": 99}


def test_text_is_split_without_loss() -> None:
    text = "x" * 4100
    parts = split_telegram_text(text)
    assert len(parts) == 2
    assert "".join(parts) == text
    assert all(len(part) <= 4096 for part in parts)


def test_text_split_preserves_boundary_whitespace_exactly() -> None:
    text = ("абзац " * 900) + "\n\nФинал  с  пробелами"
    parts = split_telegram_text(text, limit=128)
    assert len(parts) > 2
    assert "".join(parts) == text
    assert all(len(part) <= 128 for part in parts)


def test_photo_and_long_text_publish_separately() -> None:
    bot = FakeBot()
    publisher = TelegramPublisher(lambda: bot, lambda chat: str(chat))
    image = b"\x89PNG\r\n\x1a\nimage"
    result = asyncio.run(publisher.publish(chat_id="1", text="x" * 1025, photo_bytes=image))
    assert result.mode == "photo_then_text"
    assert bot.photos[0]["caption"] == ""
    assert bot.photos[0]["mime_type"] == "image/png"
    assert bot.messages == ["x" * 1025]


def test_photo_mime_validation_rejects_non_image() -> None:
    with pytest.raises(ValueError, match="PNG"):
        validate_photo_bytes(b"not-an-image")


def test_photo_url_rejects_embedded_credentials() -> None:
    with pytest.raises(ValueError, match="credentials"):
        validate_photo_url("https://user:password@example.com/image.png")


def test_filename_rejects_header_injection_characters() -> None:
    with pytest.raises(ValueError, match="control characters"):
        validate_filename("image.png\r\nX-Evil: yes")


def test_publisher_requires_message_id_from_telegram() -> None:
    class MissingIdBot(FakeBot):
        async def send_message(self, *, chat_id: str, text: str) -> dict:
            self.messages.append(text)
            return {}

    publisher = TelegramPublisher(lambda: MissingIdBot(), lambda chat: str(chat))
    with pytest.raises(RuntimeError, match="message_id"):
        asyncio.run(publisher.publish(chat_id="1", text="hello"))


def test_schedule_persists_cancel_and_idempotency(tmp_path) -> None:
    store = TelegramScheduleStore(tmp_path / "telegram.sqlite3")
    when = utc_now() + timedelta(minutes=1)
    first = store.schedule(
        kind="post",
        chat_id="1",
        payload={"text": "hello"},
        scheduled_for=when,
        idempotency_key="same",
    )
    reloaded = TelegramScheduleStore(tmp_path / "telegram.sqlite3")
    duplicate = reloaded.schedule(
        kind="post",
        chat_id="1",
        payload={"text": "hello"},
        scheduled_for=when,
        idempotency_key="same",
    )
    assert duplicate.id == first.id
    assert reloaded.cancel(first.id).status == "cancelled"


@pytest.mark.skipif(os.name != "posix", reason="POSIX file mode test")
def test_scheduler_database_is_owner_only_on_posix(tmp_path) -> None:
    path = tmp_path / "telegram.sqlite3"
    TelegramScheduleStore(path)
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600


@pytest.mark.skipif(os.name != "posix", reason="POSIX file mode test")
def test_poll_database_is_owner_only_on_posix(tmp_path) -> None:
    path = tmp_path / "polls.sqlite3"
    TelegramPollStore(path)
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600


@pytest.mark.skipif(os.name != "posix", reason="POSIX symlink semantics")
def test_scheduler_rejects_symlink_database_path(tmp_path) -> None:
    target = tmp_path / "real.sqlite3"
    TelegramScheduleStore(target)
    link = tmp_path / "alias.sqlite3"
    link.symlink_to(target)

    with pytest.raises(RuntimeError, match="must_not_be_symlink"):
        TelegramScheduleStore(link)


@pytest.mark.skipif(os.name != "posix", reason="POSIX symlink semantics")
def test_poll_store_rejects_symlink_database_path(tmp_path) -> None:
    target = tmp_path / "real-polls.sqlite3"
    TelegramPollStore(target)
    link = tmp_path / "alias-polls.sqlite3"
    link.symlink_to(target)

    with pytest.raises(RuntimeError, match="must_not_be_symlink"):
        TelegramPollStore(link)


def test_idempotency_key_cannot_alias_different_delivery(tmp_path) -> None:
    store = TelegramScheduleStore(tmp_path / "telegram.sqlite3")
    when = utc_now() + timedelta(minutes=1)
    store.schedule(
        kind="post",
        chat_id="1",
        payload={"text": "original"},
        scheduled_for=when,
        idempotency_key="same",
    )

    with pytest.raises(ValueError, match="idempotency_key_conflict"):
        store.schedule(
            kind="post",
            chat_id="1",
            payload={"text": "different"},
            scheduled_for=when,
            idempotency_key="same",
        )


def test_scheduler_delivers_once_and_stores_result(tmp_path) -> None:
    store = TelegramScheduleStore(tmp_path / "telegram.sqlite3")
    item = store.schedule(
        kind="post",
        chat_id="1",
        payload={"text": "hello"},
        scheduled_for=utc_now() + timedelta(seconds=1),
        idempotency_key="once",
    )
    calls: list[str] = []

    async def deliver(job):
        calls.append(job.id)
        return 42

    scheduler = TelegramScheduler(store, deliver)
    assert asyncio.run(scheduler.run_due(utc_now() + timedelta(seconds=2))) == 1
    assert asyncio.run(scheduler.run_due(utc_now() + timedelta(seconds=3))) == 0
    assert calls == [item.id]
    assert store.get(item.id).status == "sent"
    assert store.get(item.id).message_id == 42


def test_scheduler_persists_error_code_not_exception_text(tmp_path) -> None:
    store = TelegramScheduleStore(tmp_path / "telegram.sqlite3")
    item = store.schedule(
        kind="post",
        chat_id="1",
        payload={},
        scheduled_for=utc_now() + timedelta(seconds=1),
        idempotency_key="bad",
    )

    async def broken(_):
        raise RuntimeError("secret-token-and-client-caption-must-not-be-persisted")

    asyncio.run(TelegramScheduler(store, broken).run_due(utc_now() + timedelta(seconds=2)))
    failed = store.get(item.id)
    assert failed.status == "failed"
    assert failed.error == "delivery_runtimeerror"
    assert "secret-token" not in (failed.error or "")


def test_restart_fails_closed_for_uncertain_sending_job(tmp_path) -> None:
    path = tmp_path / "telegram.sqlite3"
    store = TelegramScheduleStore(path)
    interrupted = store.schedule(
        kind="post",
        chat_id="1",
        payload={},
        scheduled_for=utc_now() + timedelta(seconds=1),
        idempotency_key="interrupted",
    )
    store.claim_due(utc_now() + timedelta(seconds=2))
    reloaded = TelegramScheduleStore(path)
    recovered = reloaded.get(interrupted.id)
    assert recovered.status == "failed"
    assert recovered.error == "interrupted_before_delivery_confirmation"


def test_poll_validation_matches_bot_api_10_contract() -> None:
    single = validate_poll(question="Only?", options=["A"])
    assert single["options"] == ["A"]

    quiz = validate_poll(
        question="Select correct",
        options=["A", "B", "C"],
        poll_type="quiz",
        correct_option_ids=[2, 0, 2],
        allows_multiple_answers=True,
        explanation="Because",
    )
    assert quiz["correct_option_ids"] == [0, 2]

    with pytest.raises(ValueError, match="1 to 12"):
        validate_poll(question="Too many", options=[str(i) for i in range(13)])
    with pytest.raises(ValueError, match="multiple correct"):
        validate_poll(
            question="Next?",
            options=["A", "B"],
            poll_type="quiz",
            correct_option_ids=[0, 1],
            allows_multiple_answers=False,
        )


def test_poll_store_normalizes_results_and_answers(tmp_path) -> None:
    store = TelegramPollStore(tmp_path / "telegram.sqlite3")
    store.record_sent(
        poll={"id": "poll-1", "question": "Q", "options": []},
        chat_id="-1001",
        message_id=1,
    )
    assert store.ingest_update(
        {
            "poll": {
                "id": "poll-1",
                "question": "Q",
                "options": [{"text": "A", "voter_count": 1}],
                "total_voter_count": 1,
            }
        }
    )
    assert store.ingest_update(
        {"poll_answer": {"poll_id": "poll-1", "user": {"id": 7}, "option_ids": [0]}}
    )
    result = store.results("poll-1")
    assert result["poll"]["total_voter_count"] == 1
    assert result["answers"] == [{"user_id": "7", "option_ids": [0]}]


def test_poll_store_ignores_answers_for_unknown_poll(tmp_path) -> None:
    store = TelegramPollStore(tmp_path / "telegram.sqlite3")
    assert not store.ingest_update(
        {"poll_answer": {"poll_id": "unknown", "user": {"id": 7}, "option_ids": [0]}}
    )
