from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from typing import Any

import httpx

from .comment_pipeline import process_update
from .config import settings
from .telegram_errors import TelegramDeliveryUncertainError
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

    def _egress_config(self) -> tuple[str, str] | None:
        if not settings.telegram_egress_enabled:
            return None

        url = (settings.telegram_egress_url or "").strip()
        if not url:
            supabase_url = os.getenv("JAFAR_SUPABASE_URL", "").strip().rstrip("/")
            if supabase_url:
                url = f"{supabase_url}/functions/v1/telegram-egress"

        auth_token = (settings.telegram_egress_auth_token or "").strip()
        if not auth_token:
            auth_token = os.getenv("JAFAR_SUPABASE_SERVICE_ROLE_KEY", "").strip()

        if not url.startswith("https://"):
            raise RuntimeError("Telegram egress requires an HTTPS TELEGRAM_EGRESS_URL")
        if not auth_token:
            raise RuntimeError(
                "Telegram egress requires TELEGRAM_EGRESS_AUTH_TOKEN or "
                "JAFAR_SUPABASE_SERVICE_ROLE_KEY"
            )
        return url, auth_token

    async def _post(self, method: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                response = await client.post(self._url(method), **kwargs)
        except (httpx.TimeoutException, httpx.HTTPError):
            # A POST can reach Telegram even when the client never receives a response.
            # Treat transport ambiguity as uncertain delivery and never auto-retry it.
            raise TelegramDeliveryUncertainError(
                f"Telegram {method} delivery uncertain"
            ) from None

        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"Telegram {method} HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError:
            raise RuntimeError(f"Telegram {method} returned invalid JSON") from None
        if not isinstance(payload, dict):
            raise RuntimeError(f"Telegram {method} returned invalid response")
        if not payload.get("ok"):
            # Telegram's description is external input and can echo sensitive request data.
            raise RuntimeError(f"Telegram {method} API request failed")
        result = payload.get("result")
        return dict(result) if isinstance(result, dict) else {}

    async def _post_egress(
        self,
        method: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        config = self._egress_config()
        if config is None:
            raise RuntimeError("telegram_egress_not_enabled")
        url, auth_token = config

        try:
            async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {auth_token}",
                        "x-telegram-bot-token": self._bot_token,
                        "content-type": "application/json",
                    },
                    json={"action": method, **payload},
                )
        except (httpx.TimeoutException, httpx.HTTPError):
            # The Supabase relay may already have delivered the POST to Telegram.
            # Preserve the same no-auto-retry semantics as the direct transport.
            raise TelegramDeliveryUncertainError(
                f"Telegram {method} delivery uncertain"
            ) from None

        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"Telegram {method} egress HTTP {response.status_code}")
        try:
            envelope = response.json()
        except ValueError:
            raise RuntimeError(f"Telegram {method} egress returned invalid JSON") from None
        if not isinstance(envelope, dict) or not envelope.get("ok"):
            raise RuntimeError(f"Telegram {method} egress request failed")
        telegram_payload = envelope.get("telegram")
        if not isinstance(telegram_payload, dict) or not telegram_payload.get("ok"):
            raise RuntimeError(f"Telegram {method} API request failed")
        result = telegram_payload.get("result")
        return dict(result) if isinstance(result, dict) else {}

    async def send_message(self, *, chat_id: int | str, text: str) -> dict[str, Any]:
        if self._egress_config() is not None:
            return await self._post_egress(
                "sendMessage",
                {"chat_id": str(chat_id), "text": text},
            )
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

        if self._egress_config() is not None:
            payload: dict[str, Any] = {
                "chat_id": str(chat_id),
                "caption": caption,
                "filename": filename,
            }
            if photo_url:
                payload["photo_url"] = photo_url
            else:
                payload["photo_base64"] = base64.b64encode(photo_bytes or b"").decode(
                    "ascii"
                )
            return await self._post_egress("sendPhoto", payload)

        data: dict[str, Any] = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption

        files = None
        if photo_url:
            data["photo"] = photo_url
        else:
            files = {"photo": (filename, photo_bytes, mime_type)}

        return await self._post("sendPhoto", data=data, files=files)

    async def send_video(
        self,
        *,
        chat_id: int | str,
        video_bytes: bytes | None = None,
        video_url: str | None = None,
        filename: str = "video.mp4",
        caption: str = "",
    ) -> dict[str, Any]:
        """Send exactly one MP4 source through the same uncertain-POST semantics."""
        if bool(video_url) == bool(video_bytes):
            raise ValueError("provide exactly one of video_url or video_bytes")

        if self._egress_config() is not None:
            payload: dict[str, Any] = {
                "chat_id": str(chat_id),
                "caption": caption,
                "filename": filename,
            }
            if video_url:
                payload["video_url"] = video_url
            else:
                payload["video_base64"] = base64.b64encode(video_bytes or b"").decode(
                    "ascii"
                )
            return await self._post_egress("sendVideo", payload)

        data: dict[str, Any] = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption
        if video_url:
            data["video"] = video_url
            return await self._post("sendVideo", data=data)
        return await self._post(
            "sendVideo",
            data=data,
            files={"video": (filename, video_bytes, "video/mp4")},
        )

    async def send_poll(self, *, chat_id: int | str, poll: dict[str, Any]) -> dict[str, Any]:
        options = poll.get("options")
        if not isinstance(options, list):
            raise ValueError("telegram_poll_options_invalid")

        if self._egress_config() is not None:
            correct_option_ids = poll.get("correct_option_ids")
            correct_option_id: int | None = None
            if correct_option_ids is not None:
                if not isinstance(correct_option_ids, list):
                    raise ValueError("telegram_poll_correct_options_invalid")
                if len(correct_option_ids) > 1:
                    raise ValueError(
                        "telegram_quiz_egress_supports_one_correct_option"
                    )
                if correct_option_ids:
                    correct_option_id = int(correct_option_ids[0])

            payload: dict[str, Any] = {
                "chat_id": str(chat_id),
                "question": poll["question"],
                "options": [str(option) for option in options],
                "is_anonymous": bool(poll["is_anonymous"]),
                "allows_multiple_answers": bool(poll["allows_multiple_answers"]),
                "type": poll["type"],
            }
            if correct_option_id is not None:
                payload["correct_option_id"] = correct_option_id
            for key in ("explanation", "open_period", "close_date"):
                if poll.get(key) is not None:
                    payload[key] = poll[key]
            return await self._post_egress("sendPoll", payload)

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
            data["correct_option_ids"] = json.dumps(
                correct_option_ids,
                separators=(",", ":"),
            )
        for key in ("explanation", "open_period", "close_date"):
            if poll.get(key) is not None:
                data[key] = str(poll[key])
        return await self._post("sendPoll", data=data)


class TelegramRuntime:
    """Receive allowlisted Telegram updates; inbound traffic never sends automatically."""

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
        # Kept for constructor compatibility. Every external effect goes through the
        # hash-bound MCP approval/execution path, never the inbound polling task.
        del production_send
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

        logger.info(
            "Telegram inbound draft ready update=%s chat_type=%s chat=%s dry_run=%s",
            update.get("update_id"),
            str(update.get("message", {}).get("chat", {}).get("type", "unknown")),
            result.comment.chat_id,
            self.dry_run,
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
