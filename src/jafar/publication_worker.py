from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from .publication_runtime import DispatchablePublication, dispatch_publication


class PublicationRepository(Protocol):
    async def claim_due(self, now: datetime, limit: int = 10) -> list[DispatchablePublication]: ...


@dataclass(frozen=True)
class WorkerReport:
    claimed: int
    published: int
    failed: int


async def run_once(repository: PublicationRepository, sender, store, limit: int = 10) -> WorkerReport:
    now = datetime.now(timezone.utc)
    items = await repository.claim_due(now, limit)
    published = 0
    failed = 0
    for item in items:
        try:
            await dispatch_publication(item, sender, store)
            published += 1
        except Exception:
            failed += 1
    return WorkerReport(len(items), published, failed)
