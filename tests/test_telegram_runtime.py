import asyncio

from jafar import telegram_runtime as telegram_runtime_module
from jafar.telegram_runtime import TelegramRuntime


class FakeOutbound:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, bool]] = []

    async def send_text(self, chat_id: int | str, text: str, *, allowed: bool):
        self.calls.append((str(chat_id), text, allowed))


def test_runtime_routes_safe_allowlisted_comment_to_outbound(monkeypatch, tmp_path) -> None:
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
    fake = FakeOutbound()
    runtime.outbound = fake  # type: ignore[assignment]

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

    assert len(fake.calls) == 1
    chat_id, text, allowed = fake.calls[0]
    assert chat_id == "-100123"
    assert "Спасибо за вопрос" in text
    assert allowed is True


def test_runtime_drops_non_allowlisted_content_before_drafting(monkeypatch, tmp_path) -> None:
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
    fake = FakeOutbound()
    runtime.outbound = fake  # type: ignore[assignment]

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
    assert fake.calls == []


def test_runtime_does_not_send_blocked_comment(monkeypatch, tmp_path) -> None:
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
    fake = FakeOutbound()
    runtime.outbound = fake  # type: ignore[assignment]

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
    assert fake.calls == []
