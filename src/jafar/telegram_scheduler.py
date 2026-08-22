from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .telegram_bot import TelegramBot
from .telegram_dry_run_guard import require_production_publication_enabled


@dataclass(frozen=True)
class ApprovedPublication:
    chat_id: int | str
    text: str
    publish_at: datetime

    def due(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        return self.publish_at <= current


async def publish_due(bot: TelegramBot, item: ApprovedPublication, now: datetime | None = None) -> dict:
    """Publish an approved item only when due and production publication is explicitly enabled."""
    if not item.due(now):
        return {"published": False, "reason": "not_due"}
    require_production_publication_enabled()
    result = await bot.send_message(item.chat_id, item.text)
    return {"published": True, "telegram": result}
