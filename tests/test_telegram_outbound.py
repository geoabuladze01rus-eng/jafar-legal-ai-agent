import pytest

from jafar.production_guard import ProductionGuard
from jafar.telegram_outbound import TelegramOutbound


class FakeBot:
    def __init__(self):
        self.calls = []

    async def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return {"message_id": 1}


@pytest.mark.asyncio
async def test_dry_run_never_calls_telegram():
    bot = FakeBot()
    outbound = TelegramOutbound(ProductionGuard(production_send=False), bot)

    result = await outbound.send_text(123, "test", allowed=True)

    assert result.dry_run is True
    assert result.sent is False
    assert bot.calls == []


@pytest.mark.asyncio
async def test_safety_block_never_calls_telegram_in_production():
    bot = FakeBot()
    outbound = TelegramOutbound(ProductionGuard(production_send=True), bot)

    result = await outbound.send_text(123, "blocked", allowed=False)

    assert result.blocked is True
    assert result.sent is False
    assert bot.calls == []


@pytest.mark.asyncio
async def test_explicit_production_mode_calls_telegram():
    bot = FakeBot()
    outbound = TelegramOutbound(ProductionGuard(production_send=True), bot)

    result = await outbound.send_text(123, "approved", allowed=True)

    assert result.sent is True
    assert result.value == {"message_id": 1}
    assert bot.calls == [{"chat_id": 123, "text": "approved"}]
