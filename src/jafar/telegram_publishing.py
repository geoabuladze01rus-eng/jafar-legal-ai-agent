from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlparse

from .telegram_runtime import TelegramBotHttpClient

MAX_MESSAGE_CHARS = 4096
MAX_CAPTION_CHARS = 1024
MAX_PHOTO_BYTES = 10 * 1024 * 1024
_IMAGE_TYPES = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"RIFF": "image/webp",
}


def image_mime_type(content: bytes) -> str:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"RIFF") and len(content) >= 12 and content[8:12] == b"WEBP":
        return "image/webp"
    raise ValueError("photo must be a PNG, JPEG, or WebP image")


def validate_photo_bytes(content: bytes) -> str:
    if not content:
        raise ValueError("photo must not be empty")
    if len(content) > MAX_PHOTO_BYTES:
        raise ValueError("photo exceeds 10 MB limit")
    return image_mime_type(content)


def validate_photo_url(value: str) -> str:
    url = value.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("photo_url must be an absolute http(s) URL")
    if len(url) > 2048:
        raise ValueError("photo_url exceeds 2048 character limit")
    return url


def split_telegram_text(text: str, limit: int = MAX_MESSAGE_CHARS) -> list[str]:
    """Split without truncating Unicode text, preferring paragraph/word boundaries."""
    if not text:
        return []
    result: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = max(remaining.rfind("\n", 0, limit + 1), remaining.rfind(" ", 0, limit + 1))
        if cut <= 0:
            cut = limit
        result.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip(" \n")
    if remaining:
        result.append(remaining)
    return result


@dataclass(frozen=True)
class PublishResult:
    mode: str
    message_ids: list[int]
    photo_message_id: int | None = None


class TelegramPublisher:
    """Single delivery path used by immediate and scheduled publications."""

    def __init__(
        self,
        client_factory: Callable[[], TelegramBotHttpClient],
        allow_chat: Callable[[int | str], str],
    ):
        self._client_factory = client_factory
        self._allow_chat = allow_chat

    async def publish(
        self,
        *,
        chat_id: int | str,
        text: str,
        photo_url: str | None = None,
        photo_bytes: bytes | None = None,
        filename: str = "image.png",
    ) -> PublishResult:
        safe_chat_id = self._allow_chat(chat_id)  # Deliberately checked at delivery time.
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("text must not be empty")
        if bool(photo_url) and bool(photo_bytes):
            raise ValueError("provide only one of photo_url or photo_base64")
        if photo_url:
            photo_url = validate_photo_url(photo_url)
        mime_type = validate_photo_bytes(photo_bytes) if photo_bytes else None
        client = self._client_factory()

        if not photo_url and not photo_bytes:
            messages = await self._send_text(client, safe_chat_id, clean_text)
            return PublishResult("text", messages)

        caption = clean_text if len(clean_text) <= MAX_CAPTION_CHARS else ""
        photo = await client.send_photo(
            chat_id=safe_chat_id,
            caption=caption,
            photo_url=photo_url,
            photo_bytes=photo_bytes,
            filename=filename,
            mime_type=mime_type or "application/octet-stream",
        )
        photo_id = int(photo["message_id"]) if photo.get("message_id") is not None else None
        if caption:
            return PublishResult("photo_with_caption", [], photo_id)
        messages = await self._send_text(client, safe_chat_id, clean_text)
        return PublishResult("photo_then_text", messages, photo_id)

    async def _send_text(self, client: TelegramBotHttpClient, chat_id: str, text: str) -> list[int]:
        ids: list[int] = []
        for part in split_telegram_text(text):
            # A second check protects multi-part sends if policy changes mid-publication.
            safe_chat_id = self._allow_chat(chat_id)
            result = await client.send_message(chat_id=safe_chat_id, text=part)
            if result.get("message_id") is not None:
                ids.append(int(result["message_id"]))
        return ids
