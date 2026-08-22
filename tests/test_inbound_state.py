import asyncio

from jafar.inbound_state import InMemoryInboundStateStore


def test_update_is_claimed_once():
    async def run():
        store = InMemoryInboundStateStore()
        assert await store.claim_update(10) is True
        assert await store.claim_update(10) is False
    asyncio.run(run())
