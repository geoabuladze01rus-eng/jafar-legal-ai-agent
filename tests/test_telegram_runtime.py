import asyncio
import logging

from jafar import main as main_module

from jafar import telegram_runtime as telegram_runtime_module
from jafar.telegram_runtime import TelegramRuntime


def test_runtime_creates_safe_draft_signal_but_never_sends(monkeypatch, tmp_path, caplog) -> None:
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(
        telegram_runtime_module.settings,
        "telegram_scheduler_db_path",
        str(tmp_path / "telegram.sqlite3"),
    )
    monkeypatch.setattr(
        telegram_runtime_module,
        "configured_chat_ids",
        lambda _settings: ("-100123",),
    )
    runtime = TelegramRuntime("test-token", production_send=False, dry_run=False)

    update = {
        "update_id": 101,
        "message": {
            "message_id": 7,
            "chat": {"id": -100123, "type": "supergroup"},
            "from": {"id": 42, "username": "tester"},
            "text": "Почему суд отказал?",
        },
    }

    asyncio.run(runtime.handle_update(update))

    assert "Telegram inbound draft ready" in caplog.text
    assert "Почему суд отказал" not in caplog.text


def test_runtime_drops_non_allowlisted_content_before_drafting(monkeypatch, tmp_path, caplog) -> None:
    monkeypatch.setattr(
        telegram_runtime_module.settings,
        "telegram_scheduler_db_path",
        str(tmp_path / "telegram.sqlite3"),
    )
    monkeypatch.setattr(
        telegram_runtime_module,
        "configured_chat_ids",
        lambda _settings: ("-100999",),
    )
    runtime = TelegramRuntime("test-token", production_send=False, dry_run=False)

    update = {
        "update_id": 102,
        "message": {
            "message_id": 8,
            "chat": {"id": -100123, "type": "group"},
            "from": {"id": 42},
            "text": "Этот текст не должен попадать в pipeline",
        },
    }

    asyncio.run(runtime.handle_update(update))
    assert "Этот текст" not in caplog.text


def test_runtime_does_not_send_blocked_comment(monkeypatch, tmp_path, caplog) -> None:
    monkeypatch.setattr(
        telegram_runtime_module.settings,
        "telegram_scheduler_db_path",
        str(tmp_path / "telegram.sqlite3"),
    )
    monkeypatch.setattr(
        telegram_runtime_module,
        "configured_chat_ids",
        lambda _settings: ("-100123",),
    )
    runtime = TelegramRuntime("test-token", production_send=False)

    update = {
        "update_id": 103,
        "message": {
            "message_id": 9,
            "chat": {"id": -100123, "type": "group"},
            "from": {"id": 42},
            "text": "Публикую паспорт и адрес здесь",
        },
    }

    asyncio.run(runtime.handle_update(update))
    assert "draft ready" not in caplog.text


def test_exported_fastapi_lifespan_starts_runtime_only_when_polling_enabled(monkeypatch) -> None:
    events: list[str] = []

    class FakeRuntime:
        def __init__(self, token: str, *, production_send: bool = False) -> None:
            assert token == "test-token"
            assert production_send is False
            events.append("created")

        def start(self) -> None:
            events.append("started")

        async def stop(self) -> None:
            events.append("stopped")

    monkeypatch.setattr(main_module, "TelegramRuntime", FakeRuntime)
    monkeypatch.setattr(main_module.settings, "telegram_polling_enabled", True)
    monkeypatch.setattr(main_module.settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(main_module.settings, "telegram_allowed_chat_ids", "-100123")
    monkeypatch.setattr(main_module.settings, "telegram_production_send", False)
    monkeypatch.setattr(main_module.settings, "telegram_dry_run", True)

    async def exercise() -> None:
        async with main_module.lifespan(main_module.app):
            assert events == ["created", "started"]

    asyncio.run(exercise())
    assert events == ["created", "started", "stopped"]
