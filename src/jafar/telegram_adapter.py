from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class TelegramSendResult:
    message_id: int
    chat_id: str


class TelegramApiError(RuntimeError):
    pass


class TelegramBotApiSender:
    def __init__(self, bot_token: str, *, timeout: float = 20.0) -> None:
        if not bot_token:
            raise ValueError("Telegram bot token is required")
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.timeout = timeout

    async def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/{method}", json=payload)
            response.raise_for_status()
            data = response.json()
        if not data.get("ok"):
            raise TelegramApiError(data.get("description", "Telegram API request failed"))
        return data["result"]

    async def send_text(self, *, chat_id: str, text: str) -> TelegramSendResult:
        result = await self._post("sendMessage", {"chat_id": chat_id, "text": text})
        return TelegramSendResult(message_id=result["message_id"], chat_id=str(result["chat"]["id"]))

    async def send_media(self, *, chat_id: str, media_type: str, media_url: str, caption: str) -> TelegramSendResult:
        method_by_type = {"photo": "sendPhoto", "video": "sendVideo"}
        method = method_by_type.get(media_type)
        if method is None:
            raise ValueError(f"Unsupported Telegram media type: {media_type}")
        result = await self._post(method, {"chat_id": chat_id, media_type: media_url, "caption": caption})
        return TelegramSendResult(message_id=result["message_id"], chat_id=str(result["chat"]["id"]))
