from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .document_recovery import DocumentRecoveryWorker, RecoveryCandidate


@dataclass(frozen=True)
class RecoveryRun:
    started_at: datetime
    finished_at: datetime
    claimed: int


class ScheduledRecoveryRunner:
    """Scheduler-facing adapter; the deployment runtime invokes tick periodically."""

    def __init__(self, worker: DocumentRecoveryWorker) -> None:
        self.worker = worker

    def tick(self, *, limit: int = 10) -> RecoveryRun:
        started = datetime.now(timezone.utc)
        candidates: list[RecoveryCandidate] = self.worker.run_once(limit=limit)
        finished = datetime.now(timezone.utc)
        return RecoveryRun(started_at=started, finished_at=finished, claimed=len(candidates))
