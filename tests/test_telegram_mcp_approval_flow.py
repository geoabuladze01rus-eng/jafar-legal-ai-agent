from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from jafar import telegram_mcp
from jafar.config import settings
from jafar.telegram_errors import TelegramDeliveryUncertainError
from jafar.telegram_publishing import PublishResult
from jafar.telegram_scheduler import TelegramScheduler, utc_now


class FakePublisher:
    def __init__(self, *, uncertain: bool = False) -> None:
        self.uncertain = uncertain
        self.calls: list[dict[str, object]] = []

    async def publish(self, **kwargs: object) -> PublishResult:
        self.calls.append(kwargs)
        if self.uncertain:
            raise TelegramDeliveryUncertainError("synthetic uncertain delivery")
        return PublishResult("text", [117])


def _settings(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "telegram_allowed_chat_ids", "-1001")
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(settings, "telegram_scheduler_db_path", str(tmp_path / "telegram.sqlite3"))
    monkeypatch.setattr(settings, "telegram_production_send", True)
    monkeypatch.setattr(settings, "telegram_dry_run", False)
    monkeypatch.setattr(settings, "telegram_owner_approver_id", "owner-1")
    monkeypatch.setattr(settings, "environment", "production")


def test_post_requires_owner_approval_before_immediate_execution(monkeypatch, tmp_path) -> None:
    _settings(monkeypatch, tmp_path)
    fake = FakePublisher()
    monkeypatch.setattr(telegram_mcp, "_publisher", lambda: fake)

    draft = asyncio.run(telegram_mcp.telegram_create_post_draft("-1001", "hello"))
    with pytest.raises(PermissionError, match="approved state"):
        asyncio.run(telegram_mcp.telegram_execute_approved(draft["approval_id"]))

    approved = asyncio.run(
        telegram_mcp.telegram_approve_publication(
            draft["approval_id"], "owner-1", "APPROVE"
        )
    )
    assert approved["state"] == "approved"

    result = asyncio.run(telegram_mcp.telegram_execute_approved(draft["approval_id"]))
    assert result["message_id"] == 117
    assert len(fake.calls) == 1
    assert asyncio.run(telegram_mcp.telegram_get_approval(draft["approval_id"]))["state"] == "executed"


def test_scheduled_approved_post_persists_and_delivers_once(monkeypatch, tmp_path) -> None:
    _settings(monkeypatch, tmp_path)
    fake = FakePublisher()
    monkeypatch.setattr(telegram_mcp, "_publisher", lambda: fake)
    future = (utc_now() + timedelta(minutes=1)).isoformat()

    draft = asyncio.run(
        telegram_mcp.telegram_create_post_draft("-1001", "scheduled", scheduled_for=future)
    )
    asyncio.run(
        telegram_mcp.telegram_approve_publication(draft["approval_id"], "owner-1", "APPROVE")
    )
    execution = asyncio.run(telegram_mcp.telegram_execute_approved(draft["approval_id"]))
    schedule_id = execution["scheduled"]["schedule_id"]

    first_store = telegram_mcp._store()
    second_store = telegram_mcp._store()
    assert second_store.get(schedule_id).status == "pending"

    asyncio.run(
        TelegramScheduler(first_store, telegram_mcp._deliver).run_due(
            utc_now() + timedelta(minutes=2)
        )
    )
    asyncio.run(
        TelegramScheduler(second_store, telegram_mcp._deliver).run_due(
            utc_now() + timedelta(minutes=2)
        )
    )
    assert telegram_mcp._store().get(schedule_id).status == "sent"
    assert telegram_mcp._store().get(schedule_id).message_id == 117
    assert len(fake.calls) == 1


def test_uncertain_immediate_delivery_is_not_marked_executed(monkeypatch, tmp_path) -> None:
    _settings(monkeypatch, tmp_path)
    monkeypatch.setattr(telegram_mcp, "_publisher", lambda: FakePublisher(uncertain=True))
    draft = asyncio.run(telegram_mcp.telegram_create_post_draft("-1001", "uncertain"))
    asyncio.run(
        telegram_mcp.telegram_approve_publication(draft["approval_id"], "owner-1", "APPROVE")
    )

    with pytest.raises(TelegramDeliveryUncertainError):
        asyncio.run(telegram_mcp.telegram_execute_approved(draft["approval_id"]))
    status = asyncio.run(telegram_mcp.telegram_get_approval(draft["approval_id"]))
    assert status["state"] == "delivery_uncertain"


def test_unknown_chat_fails_closed_before_draft(monkeypatch, tmp_path) -> None:
    _settings(monkeypatch, tmp_path)
    with pytest.raises(PermissionError):
        asyncio.run(telegram_mcp.telegram_create_post_draft("-1009", "blocked"))


def test_remote_mcp_requires_strong_token_and_https(monkeypatch) -> None:
    monkeypatch.setattr(settings, "jafar_mcp_auth_token", "x" * 40)
    monkeypatch.setattr(settings, "jafar_mcp_public_url", "https://mcp.example.test")
    token, public_url = telegram_mcp.validate_mcp_transport_security(
        transport="streamable-http",
        host="127.0.0.1",
    )
    assert token == "x" * 40
    assert public_url == "https://mcp.example.test"

    with pytest.raises(RuntimeError, match="loopback"):
        telegram_mcp.validate_mcp_transport_security(
            transport="streamable-http",
            host="0.0.0.0",
        )
