import pytest

from jafar.telegram_bot import TelegramBot
from jafar.telegram_runtime import TelegramRuntime
from jafar.telegram_scheduler import ApprovedPublication, publish_due
from jafar.telegram_dry_run_guard import ProductionPublicationDisabled
from datetime import datetime, timezone


class FakeBot:
    async def send_message(self, *args):
        raise AssertionError("Telegram send must be blocked")

    async def send_poll(self, *args):
        raise AssertionError("Telegram poll must be blocked")


@pytest.mark.asyncio
async def test_runtime_publish_is_fail_closed(monkeypatch):
    monkeypatch.delenv("TELEGRAM_PRODUCTION_ENABLED", raising=False)
    runtime = TelegramRuntime(FakeBot())
    with pytest.raises(ProductionPublicationDisabled):
        await runtime.publish(123, "blocked")


@pytest.mark.asyncio
async def test_runtime_poll_is_fail_closed(monkeypatch):
    monkeypatch.delenv("TELEGRAM_PRODUCTION_ENABLED", raising=False)
    runtime = TelegramRuntime(FakeBot())
    with pytest.raises(ProductionPublicationDisabled):
        await runtime.poll(123, "question", ["a", "b"])


@pytest.mark.asyncio
async def test_scheduler_is_fail_closed(monkeypatch):
    monkeypatch.delenv("TELEGRAM_PRODUCTION_ENABLED", raising=False)
    item = ApprovedPublication(123, "blocked", datetime.now(timezone.utc))
    with pytest.raises(ProductionPublicationDisabled):
        await publish_due(FakeBot(), item)
