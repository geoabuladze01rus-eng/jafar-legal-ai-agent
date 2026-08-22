import pytest

from jafar.production_guard import ProductionGuard


@pytest.mark.asyncio
async def test_default_mode_is_dry_run_and_sender_is_not_called():
    called = False

    async def sender():
        nonlocal called
        called = True
        return "sent"

    result = await ProductionGuard(production_send=False).execute(sender, allowed=True)

    assert result.sent is False
    assert result.dry_run is True
    assert result.blocked is False
    assert result.reason == "dry_run"
    assert called is False


@pytest.mark.asyncio
async def test_safety_block_prevents_sender_even_in_production():
    called = False

    async def sender():
        nonlocal called
        called = True
        return "sent"

    result = await ProductionGuard(production_send=True).execute(sender, allowed=False)

    assert result.sent is False
    assert result.blocked is True
    assert result.reason == "safety_gate_blocked"
    assert called is False


@pytest.mark.asyncio
async def test_production_mode_calls_sender_when_explicitly_enabled():
    async def sender():
        return "telegram-message-id"

    result = await ProductionGuard(production_send=True).execute(sender, allowed=True)

    assert result.sent is True
    assert result.dry_run is False
    assert result.blocked is False
    assert result.value == "telegram-message-id"
