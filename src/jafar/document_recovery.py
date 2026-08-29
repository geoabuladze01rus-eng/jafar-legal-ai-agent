from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


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
            except Exception:  # noqa: BLE001, S112
                continue
        return candidates
