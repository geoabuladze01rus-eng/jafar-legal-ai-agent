from __future__ import annotations

from dataclasses import dataclass

from .publication_recovery import recover_stale_claims
from .publication_worker import run_once


@dataclass(frozen=True)
class CycleReport:
    recovered: int
    claimed: int
    published: int
    failed: int


async def run_cycle(repository, sender, store, *, limit: int = 10, lease_seconds: int = 300) -> CycleReport:
    recovered = await recover_stale_claims(repository, lease_seconds)
    report = await run_once(repository, sender, store, limit)
    return CycleReport(
        recovered=recovered,
        claimed=report.claimed,
        published=report.published,
        failed=report.failed,
    )
