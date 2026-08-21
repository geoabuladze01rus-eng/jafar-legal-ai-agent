from __future__ import annotations

from typing import Any

import httpx

from .publication_dispatch import TelegramSendResult


class TelegramBotAPI:
    def __init__(self, bot_token: str, timeout: float = 20.0) -> None:
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.timeout = timeout

    async def _call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/{method}", data=payload)
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                raise RuntimeError(data.get("description", "Telegram API error"))
            return data["result"]

    async def send_text(self, *, chat_id: str, text: str) -> TelegramSendResult:
        result = await self._call("sendMessage", {"chat_id": chat_id, "text": text})
        return TelegramSendResult(message_id=result["message_id"], chat_id=str(result["chat"]["id"]))

    async def send_media(self, *, chat_id: str, media_type: str, media_url: str, caption: str) -> TelegramSendResult:
        methods = {"image": "sendPhoto", "video": "sendVideo"}
        fields = {"image": "photo", "video": "video"}
        if media_type not in methods:
            raise ValueError(f"unsupported media_type: {media_type}")
        result = await self._call(methods[media_type], {
            "chat_id": chat_id,
            fields[media_type]: media_url,
            "caption": caption,
        })
        return TelegramSendResult(message_id=result["message_id"], chat_id=str(result["chat"]["id"]))
