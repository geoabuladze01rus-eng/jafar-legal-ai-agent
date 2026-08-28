from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from jafar.telegram_polls import TelegramPollStore, validate_poll
from jafar.telegram_publishing import TelegramPublisher, split_telegram_text, validate_photo_bytes
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


def test_scheduler_marks_delivery_error_and_restart_sending_job(tmp_path) -> None:
    path = tmp_path / "telegram.sqlite3"
    store = TelegramScheduleStore(path)
    item = store.schedule(
        kind="post",
        chat_id="1",
        payload={},
        scheduled_for=utc_now() + timedelta(seconds=1),
        idempotency_key="bad",
    )

    async def broken(_):
        raise RuntimeError("Telegram rejected request")

    asyncio.run(TelegramScheduler(store, broken).run_due(utc_now() + timedelta(seconds=2)))
    assert store.get(item.id).status == "failed"
    interrupted = store.schedule(
        kind="post",
        chat_id="1",
        payload={},
        scheduled_for=utc_now() + timedelta(seconds=1),
        idempotency_key="interrupted",
    )
    store.claim_due(utc_now() + timedelta(seconds=2))
    reloaded = TelegramScheduleStore(path)
    assert reloaded.get(interrupted.id).status == "failed"
    assert "not retried" in (reloaded.get(interrupted.id).error or "")


def test_poll_validation_regular_quiz_and_bad_options() -> None:
    poll = validate_poll(
        question="Next?",
        options=["A", "B"],
        poll_type="quiz",
        correct_option_id=1,
        explanation="Because",
    )
    assert poll["correct_option_id"] == 1
    with pytest.raises(ValueError, match="2 to 10"):
        validate_poll(question="Next?", options=["only"])
    with pytest.raises(ValueError, match="cannot allow multiple"):
        validate_poll(
            question="Next?",
            options=["A", "B"],
            poll_type="quiz",
            correct_option_id=0,
            allows_multiple_answers=True,
        )


def test_poll_store_normalizes_results_and_answers(tmp_path) -> None:
    store = TelegramPollStore(tmp_path / "telegram.sqlite3")
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
