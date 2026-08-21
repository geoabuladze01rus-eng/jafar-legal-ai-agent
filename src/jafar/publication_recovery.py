from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol


class RecoveryRepository(Protocol):
    async def requeue_stale(self, now: datetime, lease_seconds: int = 300) -> int: ...


async def recover_stale_claims(repository: RecoveryRepository, lease_seconds: int = 300) -> int:
    return await repository.requeue_stale(datetime.now(timezone.utc), lease_seconds)
