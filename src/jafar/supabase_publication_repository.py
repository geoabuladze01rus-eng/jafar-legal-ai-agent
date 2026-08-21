from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from .publication_runtime import DispatchablePublication


class SupabasePublicationRepository:
    def __init__(self, url: str, service_role_key: str, timeout: float = 10.0) -> None:
        self.base = url.rstrip("/")
        self.key = service_role_key
        self.timeout = timeout

    @property
    def headers(self) -> dict[str, str]:
        return {"apikey": self.key, "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}

    async def claim_due(self, now: datetime, limit: int = 10) -> list[DispatchablePublication]:
        payload = {"p_now": now.isoformat(), "p_limit": limit}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base}/rest/v1/rpc/claim_due_telegram_publications",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            rows: list[dict[str, Any]] = response.json()
        return [
            DispatchablePublication(
                publication_id=row["id"],
                chat_id=row["chat_id"],
                body=row["body"],
                media_type=row.get("media_type"),
                media_url=row.get("media_url"),
            )
            for row in rows
        ]
