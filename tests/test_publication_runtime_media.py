import asyncio

from jafar.publication_runtime import DispatchablePublication, dispatch_publication
from jafar.dry_run_publication import DryRunSender, DryRunStore


def test_text_photo_and_video_dispatch_paths():
    async def run():
        sender = DryRunSender()
        store = DryRunStore()
        items = [
            DispatchablePublication(1, "@iznanka_ugolovki", "text"),
            DispatchablePublication(2, "@iznanka_ugolovki", "photo", "photo", "https://example.test/photo.jpg"),
            DispatchablePublication(3, "@iznanka_ugolovki", "video", "video", "https://example.test/video.mp4"),
        ]
        for item in items:
            await dispatch_publication(item, sender, store)
        return sender, store

    sender, store = asyncio.run(run())
    assert [item["type"] for item in sender.sent] == ["text", "photo", "video"]
    assert store.published == [(1, 0), (2, 0), (3, 0)]
    assert store.failed == []


def test_dispatch_failure_is_recorded_and_raised():
    class FailingSender(DryRunSender):
        async def send_text(self, *, chat_id: str, text: str):
            raise RuntimeError("simulated telegram failure")

    async def run():
        sender = FailingSender()
        store = DryRunStore()
        try:
            await dispatch_publication(
                DispatchablePublication(4, "@iznanka_ugolovki", "failure"), sender, store
            )
        except RuntimeError:
            return store
        raise AssertionError("dispatch should raise")

    store = asyncio.run(run())
    assert store.published == []
    assert store.failed == [(4, "simulated telegram failure")]
