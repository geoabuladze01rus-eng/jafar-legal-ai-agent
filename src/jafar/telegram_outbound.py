from __future__ import annotations

from dataclasses import dataclass
from os import getenv
from typing import Any

from .production_guard import OutboundResult, ProductionGuard


@dataclass(frozen=True)
class TelegramOutbound:
    """Telegram adapter that cannot bypass ProductionGuard."""

    guard: ProductionGuard
    bot: Any

    async def send_text(self, chat_id: int | str, text: str, *, allowed: bool) -> OutboundResult:
        async def sender():
            return await self.bot.send_message(chat_id=chat_id, text=text)

        return await self.guard.execute(sender, allowed=allowed)


def build_telegram_outbound(bot: Any) -> TelegramOutbound:
    production = getenv("JAFAR_PRODUCTION_SEND", "false").lower() == "true"
    return TelegramOutbound(guard=ProductionGuard(production_send=production), bot=bot)
