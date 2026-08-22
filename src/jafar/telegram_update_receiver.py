from __future__ import annotations

from typing import Any, Awaitable, Callable

import httpx


class TelegramUpdateReceiver:
    def __init__(self, bot_token: str, *, timeout: int = 30, request_timeout: float = 40.0) -> None:
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.timeout = timeout
        self.request_timeout = request_timeout

    async def fetch(self, offset: int | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"timeout": self.timeout, "allowed_updates": ["message"]}
        if offset is not None:
            params["offset"] = offset
        async with httpx.AsyncClient(timeout=self.request_timeout) as client:
            response = await client.get(f"{self.base_url}/getUpdates", params=params)
            response.raise_for_status()
            payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram getUpdates failed: {payload}")
        return list(payload.get("result", []))


async def run_polling(
    receiver: TelegramUpdateReceiver,
    handler: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    offset: int | None = None
    while True:
        updates = await receiver.fetch(offset)
        for update in updates:
            update_id = int(update["update_id"])
            await handler(update)
            offset = update_id + 1
