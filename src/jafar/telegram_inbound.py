from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TelegramComment:
    update_id: int
    chat_id: str
    message_id: int
    user_id: str | None
    username: str | None
    text: str


def normalize_update(update: dict[str, Any]) -> TelegramComment | None:
    message = update.get("message")
    if not isinstance(message, dict):
        return None
    text = message.get("text")
    chat = message.get("chat")
    if not isinstance(text, str) or not isinstance(chat, dict):
        return None
    if chat.get("type") not in {"group", "supergroup"}:
        return None
    sender = message.get("from") or {}
    return TelegramComment(
        update_id=int(update.get("update_id", 0)),
        chat_id=str(chat.get("id")),
        message_id=int(message.get("message_id", 0)),
        user_id=str(sender["id"]) if sender.get("id") is not None else None,
        username=sender.get("username"),
        text=text.strip(),
    )
