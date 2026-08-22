import pytest

from jafar.comment_classifier import CommentIntent
from jafar.inbound_worker import TelegramInboundWorker


class FakeState:
    def __init__(self):
        self.claimed = set()

    async def claim_update(self, update_id: int) -> bool:
        if update_id in self.claimed:
            return False
        self.claimed.add(update_id)
        return True


class FakeAudit:
    def __init__(self):
        self.results = []

    async def write(self, result):
        self.results.append(result)


@pytest.mark.asyncio
async def test_sensitive_comment_is_blocked(monkeypatch):
    worker = TelegramInboundWorker(FakeState(), FakeAudit())
    from jafar.comment_pipeline import process_update
    monkeypatch.setattr(
        "jafar.inbound_worker.process_update",
        lambda update: process_update({"text": "Следователь вызвал меня на допрос"}),
    )
    result = await worker.handle_update({"update_id": 100})
    assert result.blocked_by_safety_gate is True
    assert result.processed is False
    assert result.result is not None
    assert result.result.draft.intent is CommentIntent.ESCALATE


@pytest.mark.asyncio
async def test_duplicate_update_is_not_processed_twice(monkeypatch):
    worker = TelegramInboundWorker(FakeState(), FakeAudit())
    monkeypatch.setattr(
        "jafar.inbound_worker.process_update",
        lambda update: None,
    )
    first = await worker.handle_update({"update_id": 101})
    second = await worker.handle_update({"update_id": 101})
    assert first.duplicate is False
    assert second.duplicate is True
