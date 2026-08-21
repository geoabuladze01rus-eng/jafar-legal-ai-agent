from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from .comment_router import route_comment
from .config import settings
from .editorial_store import EditorialEvent
from .supabase_store import SupabaseStore

router = APIRouter(prefix="/telegram", tags=["telegram"])


def _valid_secret(header_value: str | None) -> bool:
    expected = settings.telegram_webhook_secret
    if not expected:
        return True
    return bool(header_value) and hmac.compare_digest(header_value, expected)


def _store() -> SupabaseStore | None:
    if not settings.supabase_url or not settings.supabase_service_key:
        return None
    return SupabaseStore(settings.supabase_url, settings.supabase_service_key)


@router.post("/webhook")
async def receive_telegram_update(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, Any]:
    if not _valid_secret(x_telegram_bot_api_secret_token):
        raise HTTPException(status_code=403, detail="invalid Telegram webhook secret")

    update = await request.json()
    update_id = update.get("update_id")
    message = update.get("message") or update.get("channel_post") or {}
    text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    sender = message.get("from") or {}

    store = _store()
    if store:
        await store.save_event(EditorialEvent(
            event_type="telegram_update",
            external_id=str(update_id) if update_id is not None else None,
            status="received",
            payload=update,
        ))

    if not text:
        return {"ok": True, "action": "ignore"}

    route = route_comment(text)
    if store and route.action in {"queue_for_review", "notify_owner"}:
        await store.queue_comment(
            text=text,
            route=route.action,
            chat_id=str(chat.get("id")) if chat.get("id") is not None else None,
            message_id=message.get("message_id"),
            author_id=sender.get("id"),
            update_id=update_id,
        )

    return {
        "ok": True,
        "action": route.action,
        "reason": route.reason,
        "persisted": store is not None,
    }
