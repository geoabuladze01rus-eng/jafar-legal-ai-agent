from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(request: Request) -> dict[str, object]:
    """Receive Telegram updates.

    The handler intentionally does not send an automatic legal answer here.
    Updates are classified first; sensitive or client-like messages must pass
    the approval gate before any response is sent.
    """
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
