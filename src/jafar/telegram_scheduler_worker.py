"""Run this alongside the standalone MCP HTTP server when FastAPI is not running."""

from __future__ import annotations

import asyncio
import signal

from .telegram_mcp import _deliver, _store
from .telegram_scheduler import TelegramScheduler


async def main() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    await TelegramScheduler(_store(), _deliver).serve(stop)


if __name__ == "__main__":
    asyncio.run(main())
