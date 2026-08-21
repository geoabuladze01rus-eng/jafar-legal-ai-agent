from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EditorialEvent:
    event_type: str
    external_id: str | None
    status: str
    payload: dict[str, Any]


class EditorialStore:
    """Storage contract for the Telegram editorial engine.

    The runtime can provide a Supabase implementation without coupling the
    editorial policy to a particular database SDK.
    """

    async def save_event(self, event: EditorialEvent) -> None:
        raise NotImplementedError

    async def queue_comment(self, *, text: str, route: str, chat_id: str | None = None,
                            message_id: int | None = None, author_id: int | None = None,
                            update_id: int | None = None) -> None:
        raise NotImplementedError

    async def save_publication(self, *, chat_id: str, body: str, title: str | None = None,
                               status: str = "draft", scheduled_at: str | None = None) -> None:
        raise NotImplementedError
