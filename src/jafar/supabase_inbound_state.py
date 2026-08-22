from __future__ import annotations

from typing import Any

import httpx


class SupabaseInboundStateStore:
    def __init__(self, url: str, service_key: str, *, timeout: float = 15.0) -> None:
        self.base_url = url.rstrip("/")
        self.service_key = service_key
        self.timeout = timeout

    async def claim_update(self, update_id: int) -> bool:
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        payload: dict[str, Any] = {"update_id": update_id}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/rest/v1/telegram_inbound_updates",
                headers=headers,
                json=payload,
            )
        if response.status_code == 201:
            return True
        if response.status_code in (409, 23505):
            return False
        response.raise_for_status()
        return False
