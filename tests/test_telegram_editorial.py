import asyncio
from pathlib import Path

from jafar.editorial_autopost import (
    EditorialAutopostService,
    EditorialDraft,
    EditorialQueueStore,
    EditorialRequest,
    EditorialRisk,
)
from jafar.telegram_editorial import TelegramEditorialController


class FakeTextProvider:
    def generate(self, request: EditorialRequest) -> EditorialDraft:
        return EditorialDraft(
            title="Что происходит до возбуждения дела",
            hook="Проверка уже идёт, хотя номера уголовного дела ещё нет.",
            body="Материал объясняет общий механизм без сведений о текущем доверителе.",
            image_prompt="Стол следователя, закрытая папка, холодный свет.",
            legal_claims=[],
            risk=EditorialRisk.GREEN,
            risk_flags=[],
            author_value_add="Практический взгляд изнутри системы.",
        )


class FakeImageProvider:
    def generate(self, image_prompt: str) -> bytes:
        return b"x" * 12000


class FakeBot:
    def __init__(self) -> None:
        self.messages = []
        self.photos = []
        self.callbacks = []

    async def send_message(self, *, chat_id, text, reply_markup=None):
        self.messages.append((str(chat_id), text, reply_markup))
        return {"message_id": len(self.messages)}

    async def send_photo(
        self,
        *,
        chat_id,
        photo,
        filename="editorial.jpg",
        caption=None,
        reply_markup=None,
    ):
        self.photos.append((str(chat_id), photo, filename, caption, reply_markup))
        return {"message_id": len(self.photos)}

    async def answer_callback_query(self, *, callback_query_id, text=None):
        self.callbacks.append((callback_query_id, text))
        return {}


def _controller(tmp_path: Path, *, auto_publish_green: bool, channel_send_enabled: bool):
    bot = FakeBot()
    service = EditorialAutopostService(FakeTextProvider(), FakeImageProvider())
    controller = TelegramEditorialController(
        bot=bot,
        service=service,
        store=EditorialQueueStore(tmp_path / "queue.sqlite3"),
        owner_user_id="123",
        owner_chat_id="123",
        channel_id="@channel",
        auto_publish_green=auto_publish_green,
        channel_send_enabled=channel_send_enabled,
    )
    return bot, controller


def test_green_post_is_sent_for_owner_review_by_default(tmp_path: Path) -> None:
    bot, controller = _controller(
        tmp_path,
        auto_publish_green=False,
        channel_send_enabled=True,
    )
    request = EditorialRequest(topic="Тест", source_text="Безопасный редакционный бриф.")

    payload = asyncio.run(controller.create_post(request))

    assert payload["risk"] == "green"
    assert len(bot.photos) == 1
    assert bot.photos[0][0] == "123"
    assert len(bot.messages) == 1
    keyboard = bot.messages[0][2]
    assert keyboard["inline_keyboard"][0][0]["text"] == "✅ Опубликовать"


def test_green_autopublish_posts_photo_then_text(tmp_path: Path) -> None:
    bot, controller = _controller(
        tmp_path,
        auto_publish_green=True,
        channel_send_enabled=True,
    )
    request = EditorialRequest(topic="Тест", source_text="Безопасный редакционный бриф.")

    payload = asyncio.run(controller.create_post(request))

    assert payload["status"] == "published"
    assert bot.photos[0][0] == "@channel"
    assert bot.messages[0][0] == "@channel"


def test_unauthorized_callback_cannot_publish(tmp_path: Path) -> None:
    bot, controller = _controller(
        tmp_path,
        auto_publish_green=False,
        channel_send_enabled=True,
    )
    request = EditorialRequest(topic="Тест", source_text="Безопасный редакционный бриф.")
    payload = asyncio.run(controller.create_post(request))

    update = {
        "callback_query": {
            "id": "cb1",
            "from": {"id": 999},
            "data": f"editorial:publish:{payload['publication_id']}",
        }
    }
    handled = asyncio.run(controller.handle_callback(update))

    assert handled is True
    assert bot.callbacks[-1][1] == "Недостаточно прав."
    assert all(chat_id != "@channel" for chat_id, *_ in bot.messages)
