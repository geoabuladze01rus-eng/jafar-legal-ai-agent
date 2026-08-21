from __future__ import annotations

from typing import Any

import httpx


class TelegramBotError(RuntimeError):
    """Raised when Telegram Bot API returns an unsuccessful response."""


class TelegramBotClient:
    """Small async Telegram Bot API client using the existing httpx dependency."""

    def __init__(self, token: str, timeout: float = 20.0) -> None:
        if not token:
            raise ValueError("Telegram bot token is required")
        self._base_url = f"https://api.telegram.org/bot{token}"
        self._timeout = timeout

    async def _call(self, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base_url}/{method}", json=payload or {})
            response.raise_for_status()
            data = response.json()
        if not data.get("ok"):
            raise TelegramBotError(data.get("description", "Telegram API error"))
        return data["result"]

    async def get_me(self) -> dict[str, Any]:
        return await self._call("getMe")

    async def get_chat(self, chat_id: str | int) -> dict[str, Any]:
        return await self._call("getChat", {"chat_id": chat_id})

    async def send_message(self, chat_id: str | int, text: str, *, disable_web_page_preview: bool = True) -> dict[str, Any]:
        return await self._call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": disable_web_page_preview,
            },
        )

    async def send_poll(
        self,
        chat_id: str | int,
        question: str,
        options: list[str],
        *,
        is_anonymous: bool = True,
        allows_multiple_answers: bool = False,
    ) -> dict[str, Any]:
        if not 2 <= len(options) <= 10:
            raise ValueError("Telegram polls require between 2 and 10 options")
        return await self._call(
            "sendPoll",
            {
                "chat_id": chat_id,
                "question": question,
                "options": options,
                "is_anonymous": is_anonymous,
                "allows_multiple_answers": allows_multiple_answers,
            },
        )

    async def set_webhook(self, url: str, *, secret_token: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"url": url}
        if secret_token:
            payload["secret_token"] = secret_token
        return await self._call("setWebhook", payload)
