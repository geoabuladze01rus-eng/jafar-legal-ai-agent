from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .document_recovery import DocumentRecoveryWorker, RecoveryCandidate


@dataclass(frozen=True)
class RecoveryRun:
    started_at: datetime
    finished_at: datetime
    claimed: int
    status: str = "completed"
    error: str | None = None


class ScheduledRecoveryRunner:
    """Scheduler-facing adapter with optional Supabase heartbeat persistence."""

    def __init__(self, worker: DocumentRecoveryWorker, heartbeat_store: object | None = None) -> None:
        self.worker = worker
        self.heartbeat_store = heartbeat_store

    def tick(self, *, limit: int = 10) -> RecoveryRun:
        started = datetime.now(UTC)
        try:
            candidates: list[RecoveryCandidate] = self.worker.run_once(limit=limit)
            finished = datetime.now(UTC)
            run = RecoveryRun(started_at=started, finished_at=finished, claimed=len(candidates))
        except Exception as exc:
            finished = datetime.now(UTC)
            run = RecoveryRun(started_at=started, finished_at=finished, claimed=0, status="failed", error=f"{type(exc).__name__}: {exc}")
        if self.heartbeat_store is not None:
            self.heartbeat_store.record(run)
        if run.status == "failed":
            raise RuntimeError(run.error or "recovery worker failed")
        return run
