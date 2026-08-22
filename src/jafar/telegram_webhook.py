from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException, Request

from .config import settings

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, object]:
    """Receive Telegram updates with fail-closed webhook authentication.

    The handler never sends an automatic legal answer. Updates are classified
    first; sensitive or client-like messages must pass the approval gate.
    """
    expected = settings.telegram_webhook_secret
    if not expected or not x_telegram_bot_api_secret_token or not hmac.compare_digest(
        x_telegram_bot_api_secret_token, expected
    ):
        raise HTTPException(status_code=403, detail="invalid Telegram webhook secret")

    update = await request.json()
    message = update.get("message") or update.get("channel_post") or {}
    text = (message.get("text") or "").strip()

    if not text:
        return {"ok": True, "action": "ignore"}

    lowered = text.lower()
    sensitive_markers = (
        "задержали",
        "обыск",
        "уголовное дело",
        "следователь",
        "суд",
        "адвокат",
        "срочно",
    )
    needs_review = any(marker in lowered for marker in sensitive_markers)

    return {
        "ok": True,
        "action": "review" if needs_review else "classify",
        "text_length": len(text),
    }
