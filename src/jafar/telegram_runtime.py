from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from .comment_pipeline import process_update
from .production_guard import ProductionGuard
from .telegram_outbound import TelegramOutbound
from .telegram_update_receiver import TelegramUpdateReceiver, run_polling

logger = logging.getLogger(__name__)


class TelegramBotHttpClient:
    """Minimal Telegram Bot API client used by the runtime adapter."""

    def __init__(self, bot_token: str, *, request_timeout: float = 40.0) -> None:
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.request_timeout = request_timeout

    async def send_message(self, *, chat_id: int | str, text: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.request_timeout) as client:
            response = await client.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
            response.raise_for_status()
            payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram sendMessage failed: {payload}")
        return dict(payload.get("result") or {})


class TelegramRuntime:
    """Connect Telegram polling, the comment pipeline, safety and outbound delivery."""

    def __init__(
        self,
        bot_token: str,
        *,
        production_send: bool = False,
        dry_run: bool = True,
    ) -> None:
        self.receiver = TelegramUpdateReceiver(bot_token)
        self.bot = TelegramBotHttpClient(bot_token)
        self.dry_run = dry_run
        self.outbound = TelegramOutbound(
            guard=ProductionGuard(production_send=production_send and not dry_run),
            bot=self.bot,
        )
        self._task: asyncio.Task[None] | None = None

    async def handle_update(self, update: dict[str, Any]) -> None:
        result = process_update(update)
        if result is None or not result.safety.allowed:
            return

        if self.dry_run:
            logger.info(
                "Telegram dry-run update=%s chat=%s intent=%s",
                update.get("update_id"),
                result.comment.chat_id,
                result.draft.intent,
            )
            return

        await self.outbound.send_text(
            result.comment.chat_id,
            result.draft.decision.draft,
            allowed=result.safety.allowed,
        )

    async def handle_error(self, update: dict[str, Any], exc: Exception) -> None:
        logger.exception("Telegram update %s failed", update.get("update_id"), exc_info=exc)

    async def run(self) -> None:
        await run_polling(self.receiver, self.handle_update, on_error=self.handle_error)

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self.run(), name="jafar-telegram-polling")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            finally:
                self._task = None
