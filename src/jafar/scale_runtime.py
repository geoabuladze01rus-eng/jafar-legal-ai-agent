from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    max_requests: int
    window_seconds: float

    def __post_init__(self) -> None:
        if self.max_requests <= 0 or self.window_seconds <= 0:
            raise ValueError("rate_limit_policy_must_be_positive")


class SlidingWindowRateLimiter:
    """Thread-safe local limiter. Production may back the same boundary with Redis."""

    def __init__(self, policy: RateLimitPolicy) -> None:
        self.policy = policy
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = RLock()

    def allow(self, key: str, *, now: float | None = None) -> bool:
        if not key.strip():
            raise ValueError("rate_limit_key_required")
        current = time.monotonic() if now is None else now
        cutoff = current - self.policy.window_seconds
        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.policy.max_requests:
                return False
            bucket.append(current)
            return True


@dataclass(frozen=True, slots=True)
class QueueJob(Generic[T]):
    job_id: str
    user_id: str
    operation: str
    payload: T
    priority: int = 100
    created_at: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        if not self.job_id.strip() or not self.user_id.strip() or not self.operation.strip():
            raise ValueError("queue_job_identity_required")


class BoundedPriorityQueue(Generic[T]):
    """Small deterministic queue primitive used before introducing external workers."""

    def __init__(self, *, max_size: int = 1000, max_per_user: int = 20) -> None:
        if max_size <= 0 or max_per_user <= 0:
            raise ValueError("queue_limits_must_be_positive")
        self.max_size = max_size
        self.max_per_user = max_per_user
        self._jobs: list[QueueJob[T]] = []
        self._ids: set[str] = set()
        self._per_user: dict[str, int] = defaultdict(int)
        self._lock = RLock()

    def enqueue(self, job: QueueJob[T]) -> None:
        with self._lock:
            if job.job_id in self._ids:
                raise ValueError("duplicate_queue_job_id")
            if len(self._jobs) >= self.max_size:
                raise RuntimeError("ai_queue_full")
            if self._per_user[job.user_id] >= self.max_per_user:
                raise RuntimeError("ai_queue_user_limit")
            self._jobs.append(job)
            self._ids.add(job.job_id)
            self._per_user[job.user_id] += 1
            self._jobs.sort(key=lambda item: (item.priority, item.created_at, item.job_id))

    def pop(self) -> QueueJob[T] | None:
        with self._lock:
            if not self._jobs:
                return None
            job = self._jobs.pop(0)
            self._ids.remove(job.job_id)
            self._per_user[job.user_id] -= 1
            if self._per_user[job.user_id] <= 0:
                self._per_user.pop(job.user_id, None)
            return job

    def size(self) -> int:
        with self._lock:
            return len(self._jobs)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.base_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("invalid_retry_policy")

    def delay_for_attempt(self, attempt: int) -> float:
        if attempt < 1:
            raise ValueError("attempt_must_be_positive")
        return min(self.base_delay_seconds * (2 ** (attempt - 1)), self.max_delay_seconds)


class SemanticResultCache:
    """Content-addressed cache that stores caller-supplied safe results only.

    Confidential prompts are never persisted by this primitive; callers provide a normalized
    fingerprint plus the safe reusable result. A deployment can swap this for Redis without
    changing the routing contract.
    """

    def __init__(self, *, ttl_seconds: float = 900.0, max_entries: int = 5000) -> None:
        if ttl_seconds <= 0 or max_entries <= 0:
            raise ValueError("cache_limits_must_be_positive")
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: dict[str, tuple[float, Any]] = {}
        self._lock = RLock()

    @staticmethod
    def fingerprint(*, operation: str, material: Any) -> str:
        encoded = json.dumps(
            {"operation": operation, "material": material},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def get(self, key: str, *, now: float | None = None) -> Any | None:
        current = time.monotonic() if now is None else now
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at <= current:
                self._entries.pop(key, None)
                return None
            return value

    def put(self, key: str, value: Any, *, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        with self._lock:
            if len(self._entries) >= self.max_entries and key not in self._entries:
                oldest = min(self._entries.items(), key=lambda item: item[1][0])[0]
                self._entries.pop(oldest, None)
            self._entries[key] = (current + self.ttl_seconds, value)


def execute_with_retry(
    operation: Callable[[], T],
    *,
    policy: RetryPolicy,
    retryable: Callable[[Exception], bool],
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    last_error: Exception | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if attempt >= policy.max_attempts or not retryable(exc):
                raise
            sleep(policy.delay_for_attempt(attempt))
    raise RuntimeError("retry_loop_exhausted") from last_error
