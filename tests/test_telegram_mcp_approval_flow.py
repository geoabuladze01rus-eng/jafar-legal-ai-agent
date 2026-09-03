from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from mcp.server import MCPServer
from mcp.server.auth.settings import AuthSettings
from starlette.testclient import TestClient

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
    monkeypatch.setattr(settings, "telegram_scheduler_enabled", True)
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
    monkeypatch.setattr(settings, "jafar_mcp_public_url", "https://mcp.example.test/mcp?token=no")
    with pytest.raises(RuntimeError, match="query"):
        telegram_mcp.validate_mcp_transport_security(
            transport="streamable-http",
            host="127.0.0.1",
        )


def test_remote_streamable_http_requires_bearer_and_does_not_echo_token() -> None:
    token = "t" * 40
    server = MCPServer(
        "test",
        auth=AuthSettings(
            issuer_url="https://mcp.example.test",
            resource_server_url="https://mcp.example.test",
            required_scopes=["jafar:telegram"],
        ),
        token_verifier=telegram_mcp._StaticTokenVerifier(token),
    )
    app = server.streamable_http_app(
        stateless_http=True,
        json_response=True,
        host="testserver",
    )
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    }
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    with TestClient(app) as client:
        denied = client.post("/mcp", headers=headers, json=initialize)
        allowed = client.post(
            "/mcp", headers={**headers, "Authorization": f"Bearer {token}"}, json=initialize
        )
    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert token not in denied.text
    assert token not in allowed.text


def test_dry_run_consumes_approval_without_calling_telegram(monkeypatch, tmp_path) -> None:
    _settings(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "telegram_dry_run", True)
    fake = FakePublisher()
    monkeypatch.setattr(telegram_mcp, "_publisher", lambda: fake)
    draft = asyncio.run(telegram_mcp.telegram_create_post_draft("-1001", "safe dry run"))
    asyncio.run(telegram_mcp.telegram_approve_publication(draft["approval_id"], "owner-1", "APPROVE"))

    result = asyncio.run(telegram_mcp.telegram_execute_approved(draft["approval_id"]))

    assert result["state"] == "dry_run_completed"
    assert fake.calls == []


def test_live_delivery_stays_fail_closed_when_production_send_is_disabled(monkeypatch, tmp_path) -> None:
    _settings(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "telegram_production_send", False)
    draft = asyncio.run(telegram_mcp.telegram_create_post_draft("-1001", "must not send"))
    asyncio.run(telegram_mcp.telegram_approve_publication(draft["approval_id"], "owner-1", "APPROVE"))

    with pytest.raises(PermissionError, match="TELEGRAM_PRODUCTION_SEND"):
        asyncio.run(telegram_mcp.telegram_execute_approved(draft["approval_id"]))

    assert asyncio.run(telegram_mcp.telegram_get_approval(draft["approval_id"]))["state"] == "approved"


def test_concurrent_execution_claims_only_one_delivery(monkeypatch, tmp_path) -> None:
    _settings(monkeypatch, tmp_path)
    fake = FakePublisher()
    monkeypatch.setattr(telegram_mcp, "_publisher", lambda: fake)
    draft = asyncio.run(telegram_mcp.telegram_create_post_draft("-1001", "one only"))
    asyncio.run(telegram_mcp.telegram_approve_publication(draft["approval_id"], "owner-1", "APPROVE"))

    async def execute_twice() -> list[object]:
        return await asyncio.gather(
            telegram_mcp.telegram_execute_approved(draft["approval_id"]),
            telegram_mcp.telegram_execute_approved(draft["approval_id"]),
            return_exceptions=True,
        )

    results = asyncio.run(execute_twice())
    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert len(fake.calls) == 1


def test_scheduler_does_not_clobber_fresh_claim_and_marks_stale_uncertain(tmp_path) -> None:
    from jafar.telegram_scheduler import TelegramScheduleStore

    store = TelegramScheduleStore(tmp_path / "scheduler.sqlite3")
    due = utc_now() - timedelta(seconds=1)
    item = store.schedule(
        kind="post",
        chat_id="-1001",
        payload={"text": "scheduled"},
        scheduled_for=due,
        idempotency_key="one",
    )
    claimed = store.claim_due(utc_now())
    assert [entry.id for entry in claimed] == [item.id]
    second_store = TelegramScheduleStore(tmp_path / "scheduler.sqlite3")
    assert second_store.get(item.id).status == "sending"
    assert second_store.recover_stale_sending(now=utc_now(), claim_timeout_seconds=120) == 0
    assert second_store.get(item.id).status == "sending"
    assert second_store.recover_stale_sending(
        now=utc_now() + timedelta(seconds=121), claim_timeout_seconds=120
    ) == 1
    assert second_store.get(item.id).status == "delivery_uncertain"
    assert second_store.claim_due(utc_now() + timedelta(days=1)) == []
