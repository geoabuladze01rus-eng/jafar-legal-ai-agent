from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class RecoveryHealth:
    completed_runs: int
    failed_runs: int
    running_runs: int
    documents_claimed: int
    last_completed_at: datetime | None
    last_failed_at: datetime | None


class RecoveryHealthStore(Protocol):
    def get_health(self) -> RecoveryHealth: ...


class RecoveryHealthService:
    def __init__(self, store: RecoveryHealthStore) -> None:
        self.store = store

    def get_health(self) -> RecoveryHealth:
        return self.store.get_health()

    def is_healthy(self, *, now: datetime, stale_after_seconds: int = 900) -> bool:
        health = self.get_health()
        if health.running_runs > 0:
            return True
        if health.last_completed_at is None:
            return False
        return (now - health.last_completed_at).total_seconds() <= stale_after_seconds
