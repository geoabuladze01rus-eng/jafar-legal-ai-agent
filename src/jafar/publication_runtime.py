from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class PublicationSender(Protocol):
    async def send_text(self, *, chat_id: str, text: str): ...
    async def send_media(self, *, chat_id: str, media_type: str, media_url: str, caption: str): ...


class PublicationStore(Protocol):
    async def mark_published(self, publication_id: int, message_id: int) -> None: ...
    async def mark_failed(self, publication_id: int, reason: str) -> None: ...


@dataclass(frozen=True)
class DispatchablePublication:
    publication_id: int
    chat_id: str
    body: str
    media_type: str | None = None
    media_url: str | None = None


async def dispatch_publication(item: DispatchablePublication, sender: PublicationSender, store: PublicationStore) -> int:
    try:
        if item.media_type and item.media_url:
            result = await sender.send_media(
                chat_id=item.chat_id,
                media_type=item.media_type,
                media_url=item.media_url,
                caption=item.body,
            )
        else:
            result = await sender.send_text(chat_id=item.chat_id, text=item.body)
        await store.mark_published(item.publication_id, result.message_id)
        return result.message_id
    except Exception as exc:
        await store.mark_failed(item.publication_id, str(exc))
        raise
