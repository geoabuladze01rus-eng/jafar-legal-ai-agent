from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from .config import settings
from .editorial_policy import decide

router = APIRouter(prefix="/telegram", tags=["telegram"])


def _valid_secret(header_value: str | None) -> bool:
    expected = settings.telegram_webhook_secret
    if not expected:
        return True
    return bool(header_value) and hmac.compare_digest(header_value, expected)


@router.post("/webhook")
async def receive_telegram_update(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, Any]:
    if not _valid_secret(x_telegram_bot_api_secret_token):
        raise HTTPException(status_code=403, detail="invalid Telegram webhook secret")

    update = await request.json()
    message = update.get("message") or update.get("channel_post") or {}
    text = (message.get("text") or "").strip()

    if not text:
        return {"ok": True, "action": "ignore"}

    decision = decide(text)
    return {
        "ok": True,
        "action": decision.level.value,
        "reason": decision.reason,
    }
