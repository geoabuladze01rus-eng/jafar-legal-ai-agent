from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from .comment_pipeline import process_update
from .config import settings
from .production_guard import ProductionGuard
from .telegram_errors import TelegramDeliveryUncertainError
from .telegram_outbound import TelegramOutbound
from .telegram_polls import TelegramPollStore
from .telegram_security import configured_chat_ids
from .telegram_update_receiver import TelegramUpdateReceiver, run_polling

logger = logging.getLogger(__name__)


def _message_chat_id(update: dict[str, Any]) -> str | None:
    message = update.get("message")
    if not isinstance(message, dict):
        return None
    chat = message.get("chat")
    if not isinstance(chat, dict) or chat.get("id") is None:
        return None
    return str(chat["id"])


class TelegramBotHttpClient:
    """Minimal Telegram Bot API client with secret-safe transport errors."""

    def __init__(self, bot_token: str, *, request_timeout: float = 40.0) -> None:
        token = bot_token.strip()
        if not token:
            raise ValueError("telegram_bot_token_required")
        self._bot_token = token
        self.request_timeout = request_timeout

    def _url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self._bot_token}/{method}"

    async def _post(self, method: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                response = await client.post(self._url(method), **kwargs)
        except (httpx.TimeoutException, httpx.HTTPError):
            # A POST can reach Telegram even when the client never receives a response.
            # Treat transport ambiguity as uncertain delivery and never auto-retry it.
            raise TelegramDeliveryUncertainError(f"Telegram {method} delivery uncertain") from None

        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"Telegram {method} HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError:
            raise RuntimeError(f"Telegram {method} returned invalid JSON") from None
        if not isinstance(payload, dict):
            raise RuntimeError(f"Telegram {method} returned invalid response")
        if not payload.get("ok"):
            description = payload.get("description")
            safe_description = description if isinstance(description, str) else "unknown error"
            raise RuntimeError(f"Telegram {method} failed: {safe_description[:300]}")
        result = payload.get("result")
        return dict(result) if isinstance(result, dict) else {}

    async def send_message(self, *, chat_id: int | str, text: str) -> dict[str, Any]:
        return await self._post("sendMessage", json={"chat_id": chat_id, "text": text})

    async def send_photo(
        self,
        *,
        chat_id: int | str,
        caption: str = "",
        photo_url: str | None = None,
        photo_bytes: bytes | None = None,
        filename: str = "image.png",
        mime_type: str = "application/octet-stream",
    ) -> dict[str, Any]:
        if bool(photo_url) == bool(photo_bytes):
            raise ValueError("provide exactly one of photo_url or photo_bytes")

        data: dict[str, Any] = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption

        files = None
        if photo_url:
            data["photo"] = photo_url
        else:
            files = {"photo": (filename, photo_bytes, mime_type)}

        return await self._post("sendPhoto", data=data, files=files)

    async def send_poll(self, *, chat_id: int | str, poll: dict[str, Any]) -> dict[str, Any]:
        options = poll.get("options")
        if not isinstance(options, list):
            raise ValueError("telegram_poll_options_invalid")
        data: dict[str, Any] = {
            "chat_id": str(chat_id),
            "question": poll["question"],
            "options": json.dumps(
                [{"text": str(option)} for option in options],
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "is_anonymous": str(bool(poll["is_anonymous"])).lower(),
            "allows_multiple_answers": str(bool(poll["allows_multiple_answers"])).lower(),
            "type": poll["type"],
        }
        correct_option_ids = poll.get("correct_option_ids")
        if correct_option_ids is not None:
            data["correct_option_ids"] = json.dumps(correct_option_ids, separators=(",", ":"))
        for key in ("explanation", "open_period", "close_date"):
            if poll.get(key) is not None:
                data[key] = str(poll[key])
        return await self._post("sendPoll", data=data)


class TelegramRuntime:
    """Connect Telegram polling, the comment pipeline, safety and outbound delivery."""

    def __init__(
        self,
        bot_token: str,
        *,
        production_send: bool = False,
        dry_run: bool = True,
        poll_identity_secret: str | None = None,
    ) -> None:
        self.receiver = TelegramUpdateReceiver(bot_token)
        self.bot = TelegramBotHttpClient(bot_token)
        self.dry_run = dry_run
        identity_secret = (
            poll_identity_secret
            if poll_identity_secret is not None
            else settings.telegram_poll_identity_secret
        )
        self.poll_store = TelegramPollStore(
            settings.telegram_scheduler_db_path,
            identity_secret=identity_secret,
        )
        self.outbound = TelegramOutbound(
            guard=ProductionGuard(production_send=production_send and not dry_run),
            bot=self.bot,
        )
        self._task: asyncio.Task[None] | None = None

    async def handle_update(self, update: dict[str, Any]) -> None:
        if self.poll_store.ingest_update(update):
            return

        chat_id = _message_chat_id(update)
        allowed_chats = set(configured_chat_ids(settings))
        if chat_id is None or chat_id not in allowed_chats:
            return

        result = process_update(update)
        if result is None or not result.safety.allowed:
            return

        if self.dry_run:
            logger.info(
                "Telegram dry-run update=%s chat=%s draft_chars=%s",
                update.get("update_id"),
                result.comment.chat_id,
                len(result.draft.decision.draft),
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
