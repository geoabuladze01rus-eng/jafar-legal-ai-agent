from __future__ import annotations

import asyncio
import json
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

    async def send_message(
        self,
        *,
        chat_id: int | str,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        async with httpx.AsyncClient(timeout=self.request_timeout) as client:
            response = await client.post(
                f"{self.base_url}/sendMessage",
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        if not body.get("ok"):
            raise RuntimeError(f"Telegram sendMessage failed: {body}")
        return dict(body.get("result") or {})

    async def send_photo(
        self,
        *,
        chat_id: int | str,
        photo: bytes,
        filename: str = "editorial.jpg",
        caption: str | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption
        if reply_markup is not None:
            data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)

        async with httpx.AsyncClient(timeout=self.request_timeout) as client:
            response = await client.post(
                f"{self.base_url}/sendPhoto",
                data=data,
                files={"photo": (filename, photo, "image/jpeg")},
            )
            response.raise_for_status()
            body = response.json()
        if not body.get("ok"):
            raise RuntimeError(f"Telegram sendPhoto failed: {body}")
        return dict(body.get("result") or {})

    async def answer_callback_query(
        self,
        *,
        callback_query_id: str,
        text: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text[:200]
        async with httpx.AsyncClient(timeout=self.request_timeout) as client:
            response = await client.post(
                f"{self.base_url}/answerCallbackQuery",
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        if not body.get("ok"):
            raise RuntimeError(f"Telegram answerCallbackQuery failed: {body}")
        return dict(body.get("result") or {})


class TelegramRuntime:
    """Connect Telegram polling, comment handling and owner-controlled editorial actions."""

    def __init__(
        self,
        bot_token: str,
        *,
        production_send: bool = False,
        dry_run: bool = True,
        editorial_controller: Any | None = None,
    ) -> None:
        self.receiver = TelegramUpdateReceiver(bot_token)
        self.bot = TelegramBotHttpClient(bot_token)
        self.dry_run = dry_run
        self.editorial_controller = editorial_controller
        self.outbound = TelegramOutbound(
            guard=ProductionGuard(production_send=production_send and not dry_run),
            bot=self.bot,
        )
        self._task: asyncio.Task[None] | None = None

    async def handle_update(self, update: dict[str, Any]) -> None:
        if "callback_query" in update and self.editorial_controller is not None:
            handled = await self.editorial_controller.handle_callback(update)
            if handled:
                return

        result = process_update(update)
        if result is None or not result.safety.allowed:
            return

        if self.dry_run:
            logger.info(
                "Telegram dry-run update=%s chat=%s draft_ready=true",
                update.get("update_id"),
                result.comment.chat_id,
            )
            return

        await self.outbound.send_text(
            result.comment.chat_id,
            result.draft.decision.draft,
            allowed=result.safety.allowed,
        )

    async def handle_error(self, update: dict[str, Any], exc: Exception) -> None:
        logger.error(
            "Telegram update %s failed error_type=%s",
            update.get("update_id"),
            type(exc).__name__,
        )

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
