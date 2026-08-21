from __future__ import annotations

from datetime import datetime, timezone

import httpx

from .publication_cycle import CycleReport


class SupabaseWorkerRunStore:
    def __init__(self, url: str, service_role_key: str, timeout: float = 10.0) -> None:
        self.base = url.rstrip("/")
        self.key = service_role_key
        self.timeout = timeout

    @property
    def headers(self) -> dict[str, str]:
        return {"apikey": self.key, "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}

    async def record(self, report: CycleReport, started_at: datetime, error: str | None = None) -> None:
        finished_at = datetime.now(timezone.utc)
        status = "failed" if error else "completed"
        payload = {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "recovered": report.recovered,
            "claimed": report.claimed,
            "published": report.published,
            "failed": report.failed,
            "status": status,
            "error": error[:1000] if error else None,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base}/rest/v1/telegram_worker_runs",
                headers={**self.headers, "Prefer": "return=minimal"},
                json=payload,
            )
            response.raise_for_status()
