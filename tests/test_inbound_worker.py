import asyncio

from jafar.inbound_state import InMemoryInboundStateStore
from jafar.inbound_worker import TelegramInboundWorker


class AuditSink:
    def __init__(self):
        self.items = []

    async def write(self, result):
        self.items.append(result)


def test_worker_processes_once_and_audits():
    async def run():
        sink = AuditSink()
        worker = TelegramInboundWorker(InMemoryInboundStateStore(), sink)
        update = {
            "update_id": 5,
            "message": {
                "message_id": 9,
                "text": "Почему суд так решил?",
                "chat": {"id": -100, "type": "supergroup"},
                "from": {"id": 2, "username": "reader"},
            },
        }
        first = await worker.handle_update(update)
        second = await worker.handle_update(update)
        assert first.processed is True
        assert first.duplicate is False
        assert second.duplicate is True
        assert len(sink.items) == 1
    asyncio.run(run())
