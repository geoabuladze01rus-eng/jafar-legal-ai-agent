from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .editorial_store import EditorialEvent, EditorialStore


@dataclass(frozen=True)
class SupabaseStore(EditorialStore):
    url: str
    service_key: str
    timeout: float = 15.0

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }

    async def _insert(self, table: str, payload: dict[str, Any]) -> None:
        endpoint = f"{self.url.rstrip('/')}/rest/v1/{table}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, headers=self._headers(), json=payload)
            response.raise_for_status()

    async def save_event(self, event: EditorialEvent) -> None:
        await self._insert("telegram_editorial_events", {
            "event_type": event.event_type,
            "external_id": event.external_id,
            "status": event.status,
            "payload": event.payload,
        })

    async def queue_comment(
        self, *, text: str, route: str, chat_id: str | None = None,
        message_id: int | None = None, author_id: int | None = None,
        update_id: int | None = None,
    ) -> None:
        await self._insert("telegram_comment_queue", {
            "telegram_update_id": update_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "author_id": author_id,
            "text": text,
            "route": route,
        })

    async def save_publication(
        self, *, chat_id: str, body: str, title: str | None = None,
        status: str = "draft", scheduled_at: str | None = None,
    ) -> None:
        await self._insert("telegram_publications", {
            "chat_id": chat_id,
            "title": title,
            "body": body,
            "status": status,
            "scheduled_at": scheduled_at,
        })
