import asyncio

from jafar.telegram_runtime import TelegramRuntime


class FakeOutbound:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, bool]] = []

    async def send_text(self, chat_id: int | str, text: str, *, allowed: bool):
        self.calls.append((str(chat_id), text, allowed))


def test_runtime_routes_safe_comment_to_outbound() -> None:
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


def test_runtime_does_not_send_blocked_comment() -> None:
    runtime = TelegramRuntime("test-token", production_send=False)
    fake = FakeOutbound()
    runtime.outbound = fake  # type: ignore[assignment]

    update = {
        "update_id": 102,
        "message": {
            "message_id": 8,
            "chat": {"id": -100123, "type": "group"},
            "from": {"id": 42},
            "text": "Публикую паспорт и адрес здесь",
        },
    }

    asyncio.run(runtime.handle_update(update))

    assert fake.calls == []
