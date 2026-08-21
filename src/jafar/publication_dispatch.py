from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TelegramSendResult:
    message_id: int
    chat_id: str


class TelegramPublicationDispatcher:
    def __init__(self, bot_token: str) -> None:
        self.bot_token = bot_token

    async def send_text(self, *, chat_id: str, text: str) -> TelegramSendResult:
        raise NotImplementedError("wire to Telegram Bot API runtime")

    async def send_media(self, *, chat_id: str, media_type: str, media_url: str, caption: str) -> TelegramSendResult:
        raise NotImplementedError("wire to Telegram Bot API runtime")
