from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class TelegramBot:
    token: str
    timeout: float = 15.0

    @property
    def base_url(self) -> str:
        return f"https://api.telegram.org/bot{self.token}"

    async def _call(self, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/{method}", json=payload or {})
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                raise RuntimeError(data.get("description", "Telegram API error"))
            return data

    async def get_me(self) -> dict[str, Any]:
        return await self._call("getMe")

    async def send_message(self, chat_id: int | str, text: str, **kwargs: Any) -> dict[str, Any]:
        payload = {"chat_id": chat_id, "text": text, **kwargs}
        return await self._call("sendMessage", payload)

    async def send_poll(
        self,
        chat_id: int | str,
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

    async def set_webhook(self, url: str, secret_token: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"url": url}
        if secret_token:
            payload["secret_token"] = secret_token
        return await self._call("setWebhook", payload)
