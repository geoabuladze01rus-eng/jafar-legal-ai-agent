from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecoveryCandidate:
    storage_path: str
    retry_attempts: int


class RecoveryStore(Protocol):
    def claim_due(self, *, limit: int) -> list[RecoveryCandidate]: ...


class RecoveryProcessor(Protocol):
    def retry(self, *, storage_path: str) -> object: ...


class DocumentRecoveryWorker:
    """Claims due failed documents and delegates retries to the safe retry service."""

    def __init__(self, store: RecoveryStore, retry_service: RecoveryProcessor) -> None:
        self.store = store
        self.retry_service = retry_service

    def run_once(self, *, limit: int = 10) -> list[RecoveryCandidate]:
        candidates = self.store.claim_due(limit=max(1, min(limit, 100)))
        for candidate in candidates:
            try:
                self.retry_service.retry(storage_path=candidate.storage_path)
            except Exception as exc:  # noqa: BLE001 - one bad document must not stop the batch.
                logger.warning(
                    "Document recovery failed retry_attempts=%s error_type=%s",
                    candidate.retry_attempts,
                    type(exc).__name__,
                )
        return candidates
