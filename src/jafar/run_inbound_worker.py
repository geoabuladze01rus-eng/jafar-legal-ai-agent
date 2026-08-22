from __future__ import annotations

import asyncio
import os

from .inbound_worker import build_supabase_inbound_worker
from .supabase_comment_audit import SupabaseCommentAuditSink
from .telegram_update_receiver import TelegramUpdateReceiver, run_polling


async def main() -> None:
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"]
    audit = SupabaseCommentAuditSink(supabase_url, supabase_key)
    worker = build_supabase_inbound_worker(supabase_url, supabase_key, audit)

    async def handle(update: dict) -> None:
        await worker.handle_update(update)

    await run_polling(TelegramUpdateReceiver(bot_token), handle)


if __name__ == "__main__":
    asyncio.run(main())
