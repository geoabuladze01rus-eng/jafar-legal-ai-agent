from __future__ import annotations

import base64
import os
from typing import Any

from mcp.server import MCPServer

from jafar.config import settings
from jafar.telegram_runtime import TelegramBotHttpClient

mcp = MCPServer("Jafar Telegram")

_MAX_PHOTO_BYTES = 10 * 1024 * 1024
_MAX_CAPTION_CHARS = 1024


def _allowed_chat_ids() -> set[str]:
    raw = settings.telegram_allowed_chat_ids
    return {item.strip() for item in raw.split(",") if item.strip()}


def _require_token() -> str:
    token = (settings.telegram_bot_token or "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    return token


def _require_allowed_chat(chat_id: int | str) -> str:
    value = str(chat_id).strip()
    allowed = _allowed_chat_ids()
    if not allowed:
        raise RuntimeError("TELEGRAM_ALLOWED_CHAT_IDS is empty; outbound access is disabled")
    if value not in allowed:
        raise PermissionError(f"Telegram chat {value} is not in the allowlist")
    return value


def _decode_photo_base64(photo_base64: str) -> bytes:
    value = photo_base64.strip()
    if value.startswith("data:"):
        _, _, value = value.partition(",")
    try:
        decoded = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise ValueError("photo_base64 is not valid base64") from exc
    if not decoded:
        raise ValueError("photo_base64 decodes to an empty file")
    if len(decoded) > _MAX_PHOTO_BYTES:
        raise ValueError("photo exceeds 10 MB limit")
    return decoded


@mcp.tool()
async def telegram_status() -> dict[str, Any]:
    """Return Jafar Telegram MCP configuration status without exposing secrets."""
    return {
        "configured": bool((settings.telegram_bot_token or "").strip()),
        "allowed_chat_ids_count": len(_allowed_chat_ids()),
        "outbound_enabled": bool(_allowed_chat_ids()),
    }


@mcp.tool()
async def telegram_send_message(chat_id: int | str, text: str) -> dict[str, Any]:
    """Send a Telegram message only to an explicitly allowlisted chat."""
    safe_chat_id = _require_allowed_chat(chat_id)
    if not text.strip():
        raise ValueError("text must not be empty")
    client = TelegramBotHttpClient(_require_token())
    result = await client.send_message(chat_id=safe_chat_id, text=text)
    return {
        "ok": True,
        "chat_id": safe_chat_id,
        "message_id": result.get("message_id"),
    }


@mcp.tool()
async def telegram_publish_post(
    chat_id: int | str,
    text: str,
    photo_url: str | None = None,
    photo_base64: str | None = None,
    filename: str = "image.png",
) -> dict[str, Any]:
    """Publish a Telegram post with optional photo to an allowlisted chat.

    Supply either photo_url or photo_base64, never both. If the text is longer
    than Telegram's photo-caption limit, the photo is posted first and the full
    text follows as a separate message.
    """
    safe_chat_id = _require_allowed_chat(chat_id)
    clean_text = text.strip()
    if not clean_text:
        raise ValueError("text must not be empty")
    if photo_url and photo_base64:
        raise ValueError("provide only one of photo_url or photo_base64")

    client = TelegramBotHttpClient(_require_token())

    if not photo_url and not photo_base64:
        result = await client.send_message(chat_id=safe_chat_id, text=clean_text)
        return {
            "ok": True,
            "chat_id": safe_chat_id,
            "message_id": result.get("message_id"),
            "mode": "text",
        }

    photo_bytes = _decode_photo_base64(photo_base64) if photo_base64 else None
    caption = clean_text if len(clean_text) <= _MAX_CAPTION_CHARS else ""
    photo_result = await client.send_photo(
        chat_id=safe_chat_id,
        caption=caption,
        photo_url=photo_url,
        photo_bytes=photo_bytes,
        filename=filename,
    )

    response: dict[str, Any] = {
        "ok": True,
        "chat_id": safe_chat_id,
        "photo_message_id": photo_result.get("message_id"),
        "mode": "photo_with_caption" if caption else "photo_then_text",
    }

    if not caption:
        text_result = await client.send_message(chat_id=safe_chat_id, text=clean_text)
        response["message_id"] = text_result.get("message_id")

    return response


if __name__ == "__main__":
    transport = os.getenv("JAFAR_MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "streamable-http":
        host = os.getenv("JAFAR_MCP_HOST", "127.0.0.1")
        port = int(os.getenv("JAFAR_MCP_PORT", "8000"))
        mcp.run(
            transport="streamable-http",
            host=host,
            port=port,
            stateless_http=True,
            json_response=True,
        )
    else:
        mcp.run()
