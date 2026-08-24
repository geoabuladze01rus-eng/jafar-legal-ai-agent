from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RecoveryJob:
    id: int
    storage_path: str
    attempts: int


class RecoveryQueue(Protocol):
    def claim(self, *, limit: int = 10) -> list[RecoveryJob]: ...
    def complete(self, *, job_id: int) -> None: ...
    def fail(self, *, job_id: int, error: str) -> None: ...


class RecoveryQueueWorker:
    def __init__(self, queue: RecoveryQueue, retry_service: object) -> None:
        self.queue = queue
        self.retry_service = retry_service

    def run_once(self, *, limit: int = 10) -> int:
        jobs = self.queue.claim(limit=max(1, min(limit, 100)))
        for job in jobs:
            try:
                self.retry_service.retry(storage_path=job.storage_path)
                self.queue.complete(job_id=job.id)
            except Exception as exc:  # noqa: BLE001 - persist failure and continue the batch.
                self.queue.fail(job_id=job.id, error=f"{type(exc).__name__}: {exc}")
        return len(jobs)
