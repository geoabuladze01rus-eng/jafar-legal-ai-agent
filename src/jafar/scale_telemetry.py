from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from threading import RLock
from typing import Mapping


_ALLOWED_EVENT_KEYS = {
    "queue_enqueued",
    "queue_rejected_full",
    "queue_rejected_user_limit",
    "queue_dequeued",
    "rate_limit_rejected",
    "cache_hit",
    "cache_miss",
    "retry_attempt",
    "provider_disabled",
    "cost_budget_rejected",
    "cost_reservation_rejected",
    "execution_claim_conflict",
    "reconciliation_candidate",
}


@dataclass(frozen=True, slots=True)
class ScaleTelemetrySnapshot:
    queue_depth: int
    executing_actions: int
    reconciliation_candidates: int
    disabled_providers: tuple[str, ...]
    counters: Mapping[str, int]


class ScaleTelemetry:
    """Small privacy-safe operational telemetry registry.

    Only bounded operational event names and aggregate counts are accepted. User IDs, matter
    IDs, prompts, legal text, payload hashes, email addresses and other client data are never
    valid telemetry dimensions here. Production can export the same snapshot to a metrics
    backend without changing the application contract.
    """

    def __init__(self) -> None:
        self._counters: Counter[str] = Counter()
        self._lock = RLock()

    def increment(self, event: str, amount: int = 1) -> None:
        normalized = event.strip().casefold()
        if normalized not in _ALLOWED_EVENT_KEYS:
            raise ValueError("unsupported_scale_telemetry_event")
        if amount <= 0:
            raise ValueError("telemetry_increment_must_be_positive")
        with self._lock:
            self._counters[normalized] += amount

    def counter(self, event: str) -> int:
        normalized = event.strip().casefold()
        if normalized not in _ALLOWED_EVENT_KEYS:
            raise ValueError("unsupported_scale_telemetry_event")
        with self._lock:
            return int(self._counters[normalized])

    def snapshot(
        self,
        *,
        queue_depth: int,
        executing_actions: int,
        reconciliation_candidates: int,
        disabled_providers: tuple[str, ...] = (),
    ) -> ScaleTelemetrySnapshot:
        if min(queue_depth, executing_actions, reconciliation_candidates) < 0:
            raise ValueError("telemetry_gauges_must_be_non_negative")
        safe_providers = tuple(
            sorted(
                {
                    provider.strip().casefold()
                    for provider in disabled_providers
                    if provider.strip()
                }
            )
        )
        with self._lock:
            counters = {
                key: int(self._counters.get(key, 0))
                for key in sorted(_ALLOWED_EVENT_KEYS)
            }
        return ScaleTelemetrySnapshot(
            queue_depth=queue_depth,
            executing_actions=executing_actions,
            reconciliation_candidates=reconciliation_candidates,
            disabled_providers=safe_providers,
            counters=counters,
        )
