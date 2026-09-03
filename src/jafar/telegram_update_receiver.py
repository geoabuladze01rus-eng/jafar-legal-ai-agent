from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx


class TelegramUpdateReceiver:
    def __init__(self, bot_token: str, *, timeout: int = 30, request_timeout: float = 40.0) -> None:
        token = bot_token.strip()
        if not token:
            raise ValueError("telegram_bot_token_required")
        self._bot_token = token
        self.timeout = timeout
        self.request_timeout = request_timeout

    def _url(self) -> str:
        return f"https://api.telegram.org/bot{self._bot_token}/getUpdates"

    async def fetch(self, offset: int | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "timeout": self.timeout,
            "allowed_updates": json.dumps(["message", "poll", "poll_answer"]),
        }
        if offset is not None:
            params["offset"] = offset
        try:
            async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                response = await client.get(self._url(), params=params)
        except httpx.TimeoutException:
            raise RuntimeError("Telegram getUpdates timed out") from None
        except httpx.HTTPError:
            raise RuntimeError("Telegram getUpdates transport failed") from None

        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"Telegram getUpdates HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError:
            raise RuntimeError("Telegram getUpdates returned invalid JSON") from None
        if not isinstance(payload, dict):
            raise RuntimeError("Telegram getUpdates returned invalid response")
        if not payload.get("ok"):
            description = payload.get("description")
            safe_description = description if isinstance(description, str) else "unknown error"
            raise RuntimeError(f"Telegram getUpdates failed: {safe_description[:300]}")
        result = payload.get("result")
        if not isinstance(result, list):
            raise RuntimeError("Telegram getUpdates returned invalid result")
        return [update for update in result if isinstance(update, dict)]


async def run_polling(
    receiver: TelegramUpdateReceiver,
    handler: Callable[[dict[str, Any]], Awaitable[None]],
    *,
    on_error: Callable[[dict[str, Any], Exception], Awaitable[None]] | None = None,
    retry_delay_seconds: float = 2.0,
) -> None:
    """Poll Telegram continuously without letting transport or update failures kill the worker."""
    if retry_delay_seconds < 0.1 or retry_delay_seconds > 60:
        raise ValueError("retry_delay_seconds must be between 0.1 and 60")

    offset: int | None = None
    while True:
        try:
            updates = await receiver.fetch(offset)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - polling must survive transient receiver failures
            if on_error is not None:
                await on_error({}, exc)
            await asyncio.sleep(retry_delay_seconds)
            continue

        for update in updates:
            raw_update_id = update.get("update_id")
            if isinstance(raw_update_id, bool) or not isinstance(raw_update_id, int):
                if on_error is not None:
                    await on_error(update, ValueError("telegram_update_id_invalid"))
                continue
            update_id = raw_update_id
            try:
                await handler(update)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - bad updates must not poison the queue
                if on_error is not None:
                    await on_error(update, exc)
            finally:
                offset = update_id + 1
