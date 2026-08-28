from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from jafar import telegram_mcp
from jafar.config import settings
from jafar.telegram_publishing import PublishResult
from jafar.telegram_scheduler import TelegramScheduler, utc_now


class FakePublisher:
    async def publish(self, **_: object) -> PublishResult:
        return PublishResult("text", [17])


class FakeClient:
    async def send_poll(self, *, chat_id: str, poll: dict) -> dict:
        return {
            "message_id": 19,
            "poll": {"id": "poll-19", "question": poll["question"], "options": []},
        }


def _settings(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "telegram_allowed_chat_ids", "-1001")
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(settings, "telegram_scheduler_db_path", str(tmp_path / "telegram.sqlite3"))


def test_mcp_publish_and_poll_tools(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _settings(monkeypatch, tmp_path)
    monkeypatch.setattr(telegram_mcp, "_publisher", lambda: FakePublisher())
    monkeypatch.setattr(telegram_mcp, "TelegramBotHttpClient", lambda _: FakeClient())
    post = asyncio.run(telegram_mcp.telegram_publish_post("-1001", "hello"))
    poll = asyncio.run(telegram_mcp.telegram_send_poll("-1001", "Next?", ["A", "B"]))
    assert post["message_id"] == 17
    assert poll == {"ok": True, "chat_id": "-1001", "message_id": 19, "poll_id": "poll-19"}
    assert asyncio.run(telegram_mcp.telegram_get_poll_results("poll-19"))["message_id"] == 19


def test_mcp_schedule_tools_and_delivery_allowlist_recheck(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    _settings(monkeypatch, tmp_path)
    future = (utc_now() + timedelta(minutes=1)).isoformat()
    scheduled = asyncio.run(
        telegram_mcp.telegram_schedule_post("-1001", "hello", future, idempotency_key="post-1")
    )
    duplicate = asyncio.run(
        telegram_mcp.telegram_schedule_post("-1001", "hello", future, idempotency_key="post-1")
    )
    assert duplicate["schedule_id"] == scheduled["schedule_id"]
    assert (
        asyncio.run(telegram_mcp.telegram_cancel_scheduled_post(scheduled["schedule_id"]))["status"]
        == "cancelled"
    )

    item = telegram_mcp._store().schedule(
        kind="post",
        chat_id="-1001",
        payload={"text": "blocked"},
        scheduled_for=utc_now() + timedelta(seconds=1),
        idempotency_key="post-allowlist",
    )
    monkeypatch.setattr(settings, "telegram_allowed_chat_ids", "-1002")
    asyncio.run(
        TelegramScheduler(telegram_mcp._store(), telegram_mcp._deliver).run_due(
            utc_now() + timedelta(seconds=2)
        )
    )
    assert telegram_mcp._store().get(item.id).status == "failed"
    assert "allowlist" in (telegram_mcp._store().get(item.id).error or "")


def test_mcp_tool_rejects_unknown_chat(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _settings(monkeypatch, tmp_path)
    with pytest.raises(PermissionError):
        asyncio.run(
            telegram_mcp.telegram_schedule_post(
                "-1009", "hello", (utc_now() + timedelta(minutes=1)).isoformat()
            )
        )
