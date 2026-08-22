import pytest

from jafar.comment_pipeline import process_update
from jafar.inbound_worker import TelegramInboundWorker
from jafar.production_guard import ProductionGuard
from jafar.telegram_outbound import TelegramOutbound


class FakeState:
    def __init__(self):
        self.claimed = set()

    async def claim_update(self, update_id):
        if update_id in self.claimed:
            return False
        self.claimed.add(update_id)
        return True


class FakeAudit:
    def __init__(self):
        self.results = []

    async def write(self, result):
        self.results.append(result)


class FakeBot:
    def __init__(self):
        self.calls = []

    async def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return {"message_id": 99}


@pytest.mark.asyncio
async def test_end_to_end_sensitive_comment_stays_dry_and_audited(monkeypatch):
    audit = FakeAudit()
    worker = TelegramInboundWorker(FakeState(), audit)
    monkeypatch.setattr(
        "jafar.inbound_worker.process_update",
        lambda update: process_update({"text": "Следователь вызвал меня на допрос"}),
    )

    inbound = await worker.handle_update({"update_id": 9001})
    assert inbound.blocked_by_safety_gate is True
    assert audit.results == [inbound.result]

    bot = FakeBot()
    outbound = TelegramOutbound(ProductionGuard(production_send=False), bot)
    outbound_result = await outbound.send_text(123, "не отправлять", allowed=False)

    assert outbound_result.blocked is True
    assert outbound_result.sent is False
    assert bot.calls == []
