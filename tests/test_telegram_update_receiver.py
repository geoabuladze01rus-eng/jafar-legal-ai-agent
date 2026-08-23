import pytest

from jafar.telegram_update_receiver import run_polling


class FakeReceiver:
    def __init__(self):
        self.offsets = []
        self.calls = 0

    async def fetch(self, offset=None):
        self.offsets.append(offset)
        self.calls += 1
        if self.calls == 1:
            return [{"update_id": 10}, {"update_id": 11}]
        raise asyncio.CancelledError


import asyncio


@pytest.mark.asyncio
async def test_polling_advances_after_handler_failure():
    receiver = FakeReceiver()
    handled = []
    errors = []

    async def handler(update):
        handled.append(update["update_id"])
        if update["update_id"] == 10:
            raise RuntimeError("boom")

    async def on_error(update, exc):
        errors.append((update["update_id"], str(exc)))

    with pytest.raises(asyncio.CancelledError):
        await run_polling(receiver, handler, on_error=on_error)

    assert handled == [10, 11]
    assert errors == [(10, "boom")]
    assert receiver.offsets == [None, 12]
