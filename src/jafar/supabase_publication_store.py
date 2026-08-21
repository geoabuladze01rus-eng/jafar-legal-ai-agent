from __future__ import annotations

from typing import Any

import httpx


class SupabasePublicationStore:
    def __init__(self, url: str, service_role_key: str, timeout: float = 10.0) -> None:
        self.base = url.rstrip("/")
        self.key = service_role_key
        self.timeout = timeout

    @property
    def headers(self) -> dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    async def _patch(self, publication_id: int, payload: dict[str, Any]) -> None:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.patch(
                f"{self.base}/rest/v1/telegram_publications",
                params={"id": f"eq.{publication_id}"},
                headers={**self.headers, "Prefer": "return=minimal"},
                json=payload,
            )
            response.raise_for_status()

    async def mark_published(self, publication_id: int, message_id: int) -> None:
        await self._patch(
            publication_id,
            {"status": "published", "telegram_message_id": message_id, "published_at": "now()"},
        )

    async def mark_failed(self, publication_id: int, reason: str) -> None:
        await self._patch(publication_id, {"status": "failed", "metrics": {"error": reason[:1000]}})
