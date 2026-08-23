from __future__ import annotations

import logging
import signal
import threading
from dataclasses import dataclass
from typing import Protocol

from .supabase_recovery_queue import RecoveryJob, SupabaseRecoveryQueue

log = logging.getLogger(__name__)


class RetryExecutor(Protocol):
    def retry(self, *, storage_path: str) -> object: ...


class RecoveryLeaseStore(Protocol):
    def heartbeat(self, *, job_id: str, worker_id: str) -> bool: ...
    def requeue_expired(self, *, limit: int = 50) -> int: ...


@dataclass(frozen=True)
class RecoveryWorkerConfig:
    worker_id: str
    batch_size: int = 5
    poll_seconds: float = 5.0
    heartbeat_seconds: float = 30.0


class RecoveryWorkerRuntime:
    """Long-running recovery worker with graceful shutdown and lease heartbeat."""

    def __init__(self, queue: SupabaseRecoveryQueue, executor: RetryExecutor,
                 config: RecoveryWorkerConfig, lease_store: RecoveryLeaseStore | None = None) -> None:
        self.queue = queue
        self.executor = executor
        self.config = config
        self.lease_store = lease_store
        self._stop = threading.Event()

    def request_shutdown(self, *_: object) -> None:
        log.info("recovery worker shutdown requested", extra={"worker_id": self.config.worker_id})
        self._stop.set()

    def run_forever(self) -> None:
        signal.signal(signal.SIGTERM, self.request_shutdown)
        signal.signal(signal.SIGINT, self.request_shutdown)
        log.info("recovery worker started", extra={"worker_id": self.config.worker_id})
        while not self._stop.is_set():
            try:
                self.queue.enqueue_due(limit=self.config.batch_size)
                if self.lease_store:
                    self.lease_store.requeue_expired(limit=50)
                jobs = self.queue.claim(worker_id=self.config.worker_id, limit=self.config.batch_size)
                for job in jobs:
                    if self._stop.is_set():
                        break
                    self._run_job(job)
            except Exception:
                log.exception("recovery worker iteration failed", extra={"worker_id": self.config.worker_id})
            self._stop.wait(self.config.poll_seconds)
        log.info("recovery worker stopped", extra={"worker_id": self.config.worker_id})

    def _run_job(self, job: RecoveryJob) -> None:
        heartbeat_stop = threading.Event()
        heartbeat_thread = None
        if self.lease_store:
            heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                args=(job, heartbeat_stop),
                daemon=True,
                name=f"recovery-heartbeat-{job.id}",
            )
            heartbeat_thread.start()
        try:
            self.executor.retry(storage_path=job.storage_path)
            self.queue.finish(job_id=job.id, worker_id=self.config.worker_id, success=True)
        except Exception as exc:
            log.exception("recovery job failed", extra={"job_id": job.id, "storage_path": job.storage_path})
            try:
                self.queue.finish(
                    job_id=job.id,
                    worker_id=self.config.worker_id,
                    success=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            except Exception:
                log.exception("recovery job completion update failed", extra={"job_id": job.id})
        finally:
            heartbeat_stop.set()
            if heartbeat_thread:
                heartbeat_thread.join(timeout=self.config.heartbeat_seconds)

    def _heartbeat_loop(self, job: RecoveryJob, stop: threading.Event) -> None:
        while not stop.wait(self.config.heartbeat_seconds):
            try:
                if not self.lease_store.heartbeat(job_id=job.id, worker_id=self.config.worker_id):
                    log.warning("recovery lease heartbeat rejected", extra={"job_id": job.id})
                    return
            except Exception:
                log.exception("recovery lease heartbeat failed", extra={"job_id": job.id})
