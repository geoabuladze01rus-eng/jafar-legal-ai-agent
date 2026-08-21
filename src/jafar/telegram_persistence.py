from __future__ import annotations

from typing import Any

from .comment_router import route_comment
from .editorial_store import EditorialEvent
from .supabase_store import SupabaseStore


async def persist_telegram_update(store: SupabaseStore, update: dict[str, Any]) -> dict[str, Any]:
    update_id = update.get("update_id")
    message = update.get("message") or update.get("channel_post") or {}
    text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = chat.get("id")

    await store.save_event(EditorialEvent(
        event_type="telegram_update",
        external_id=str(update_id) if update_id is not None else None,
        status="received",
        payload=update,
    ))

    if not text:
        return {"action": "ignore"}

    route = route_comment(text)
    if route.action != "auto_reply":
        author = message.get("from") or {}
        await store.queue_comment(
            text=text,
            route=route.action,
            chat_id=str(chat_id) if chat_id is not None else None,
            message_id=message.get("message_id"),
            author_id=author.get("id"),
            update_id=update_id,
        )

    return {"action": route.action, "route": route.level.value}
