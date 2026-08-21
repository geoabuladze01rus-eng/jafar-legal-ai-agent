from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .telegram_bot import TelegramBot


@dataclass(frozen=True)
class ApprovedPublication:
    chat_id: int | str
    text: str
    publish_at: datetime

    def due(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        return self.publish_at <= current


async def publish_due(bot: TelegramBot, item: ApprovedPublication, now: datetime | None = None) -> dict:
    """Publish only an already-approved item when its scheduled time arrives."""
    if not item.due(now):
        return {"published": False, "reason": "not_due"}
    result = await bot.send_message(item.chat_id, item.text)
    return {"published": True, "telegram": result}
