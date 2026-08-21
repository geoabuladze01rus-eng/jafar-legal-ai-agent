from __future__ import annotations

from dataclasses import dataclass

from .config import settings
from .telegram_bot import TelegramBot


@dataclass(frozen=True)
class TelegramRuntime:
    bot: TelegramBot

    @classmethod
    def from_settings(cls) -> "TelegramRuntime":
        if not settings.telegram_bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
        return cls(TelegramBot(settings.telegram_bot_token))

    async def healthcheck(self) -> dict[str, object]:
        me = await self.bot.get_me()
        return {"ok": True, "bot": me.get("result", {})}

    async def publish(self, chat_id: int | str, text: str) -> dict[str, object]:
        return await self.bot.send_message(chat_id, text)

    async def poll(self, chat_id: int | str, question: str, options: list[str]) -> dict[str, object]:
        return await self.bot.send_poll(chat_id, question, options)
