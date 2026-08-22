import pytest

from jafar.comment_classifier import CommentIntent
from jafar.comment_pipeline import CommentPipelineResult
from jafar.comment_response_engine import prepare_response
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


def make_result(intent):
    draft = prepare_response("test")
    draft = type(draft)(intent=intent, decision=draft.decision)
    return CommentPipelineResult(
        comment=None,
        draft=draft,
        audit=None,
    )


@pytest.mark.asyncio
async def test_worker_blocks_escalation(monkeypatch):
    audit = FakeAudit()
    worker = TelegramInboundWorker(FakeState(), audit)
    monkeypatch.setattr("jafar.inbound_worker.process_update", lambda update: make_result(CommentIntent.ESCALATE))
    result = await worker.handle_update({"update_id": 1})
    assert result.blocked_by_safety_gate is True
    assert result.processed is False
    assert len(audit.results) == 1


@pytest.mark.asyncio
async def test_worker_allows_question(monkeypatch):
    worker = TelegramInboundWorker(FakeState(), FakeAudit())
    monkeypatch.setattr("jafar.inbound_worker.process_update", lambda update: make_result(CommentIntent.QUESTION))
    result = await worker.handle_update({"update_id": 2})
    assert result.blocked_by_safety_gate is False
    assert result.processed is True
