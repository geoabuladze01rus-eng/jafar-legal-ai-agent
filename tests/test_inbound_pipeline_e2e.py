import asyncio

from jafar.inbound_state import InMemoryInboundStateStore
from jafar.inbound_worker import TelegramInboundWorker


class AuditSink:
    def __init__(self):
        self.items = []

    async def write(self, result):
        self.items.append(result)


def test_sensitive_comment_is_routed_to_editor_review_without_send():
    async def run():
        sink = AuditSink()
        worker = TelegramInboundWorker(InMemoryInboundStateStore(), sink)
        update = {
            "update_id": 101,
            "message": {
                "message_id": 77,
                "text": "Меня пытали при допросе, что делать?",
                "chat": {"id": -100123, "type": "supergroup"},
                "from": {"id": 42, "username": "reader"},
            },
        }
        result = await worker.handle_update(update)
        assert result.processed is True
        assert result.result is not None
        assert result.result.draft.decision.mode == "editor_review"
        assert len(sink.items) == 1

    asyncio.run(run())
