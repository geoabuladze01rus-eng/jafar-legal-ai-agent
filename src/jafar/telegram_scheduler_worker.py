"""Run this alongside the standalone MCP HTTP server when FastAPI is not running."""

from __future__ import annotations

import asyncio
import signal

from .config import settings
from .telegram_mcp import _deliver, _store
from .telegram_scheduler import TelegramScheduler
from .telegram_security import validate_telegram_settings


async def main() -> None:
    validate_telegram_settings(settings)
    if not settings.telegram_scheduler_enabled:
        raise RuntimeError(
            "Standalone Telegram scheduler requires TELEGRAM_SCHEDULER_ENABLED=true"
        )

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass

    try:
        await TelegramScheduler(
            _store(),
            _deliver,
            claim_timeout_seconds=settings.telegram_scheduler_claim_timeout_seconds,
        ).serve(stop)
    except asyncio.CancelledError:
        stop.set()
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
