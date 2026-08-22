from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

from .publication_cycle import CycleReport, run_cycle
from .publication_dispatch import TelegramSendResult
from .publication_worker_store import SupabaseWorkerRunStore
from .supabase_publication_repository import SupabasePublicationRepository
from .telegram_api import TelegramBotAPI
from .telegram_dry_run_guard import require_production_publication_enabled


class _TelegramSender:
    def __init__(self, api: TelegramBotAPI) -> None:
        self.api = api

    async def send_text(self, *, chat_id: str, text: str) -> TelegramSendResult:
        return await self.api.send_text(chat_id=chat_id, text=text)

    async def send_media(self, *, chat_id: str, media_type: str, media_url: str, caption: str) -> TelegramSendResult:
        return await self.api.send_media(chat_id=chat_id, media_type=media_type, media_url=media_url, caption=caption)


async def main() -> CycleReport:
    # Production publication is an explicit opt-in. A missing flag must never
    # result in a real Telegram send or even claiming queued publications.
    require_production_publication_enabled()

    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"]
    repository = SupabasePublicationRepository(supabase_url, supabase_key)
    sender = _TelegramSender(TelegramBotAPI(bot_token))
    store = SupabaseWorkerRunStore(supabase_url, supabase_key)
    started_at = datetime.now(timezone.utc)
    try:
        report = await run_cycle(repository, sender, store, limit=10, lease_seconds=300)
        await store.record(report, started_at)
        return report
    except Exception as exc:
        fallback = CycleReport(recovered=0, claimed=0, published=0, failed=1)
        await store.record(fallback, started_at, str(exc))
        raise


if __name__ == "__main__":
    asyncio.run(main())
