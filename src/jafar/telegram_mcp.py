from __future__ import annotations

from os import getenv
from typing import Any

from mcp.server import MCPServer

from .telegram_runtime import TelegramBotHttpClient

mcp = MCPServer("Jafar Telegram")


def _allowed_chat_ids() -> set[str]:
    raw = getenv("TELEGRAM_ALLOWED_CHAT_IDS", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def _require_token() -> str:
    token = getenv("TELEGRAM_BOT_TOKEN", "").strip()
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


@mcp.tool()
async def telegram_status() -> dict[str, Any]:
    """Return Jafar Telegram MCP configuration status without exposing secrets."""
    return {
        "configured": bool(getenv("TELEGRAM_BOT_TOKEN", "").strip()),
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


if __name__ == "__main__":
    mcp.run()
