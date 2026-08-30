import pytest

from jafar.scale_runtime import (
    BoundedPriorityQueue,
    QueueJob,
    RateLimitPolicy,
    RetryPolicy,
    SemanticResultCache,
    SlidingWindowRateLimiter,
    execute_with_retry,
)


def test_sliding_window_rate_limit_recovers_after_window() -> None:
    limiter = SlidingWindowRateLimiter(RateLimitPolicy(max_requests=2, window_seconds=10))

    assert limiter.allow("user-1", now=0)
    assert limiter.allow("user-1", now=1)
    assert not limiter.allow("user-1", now=2)
    assert limiter.allow("user-1", now=11)


def test_queue_is_bounded_and_fair_per_user() -> None:
    queue = BoundedPriorityQueue[str](max_size=3, max_per_user=2)
    queue.enqueue(QueueJob("j1", "u1", "analyze", "a", priority=50, created_at=1))
    queue.enqueue(QueueJob("j2", "u1", "analyze", "b", priority=10, created_at=2))

    with pytest.raises(RuntimeError, match="ai_queue_user_limit"):
        queue.enqueue(QueueJob("j3", "u1", "analyze", "c"))

    queue.enqueue(QueueJob("j4", "u2", "analyze", "d", priority=20, created_at=3))
    assert queue.pop().job_id == "j2"
    assert queue.pop().job_id == "j4"
    assert queue.pop().job_id == "j1"


def test_duplicate_queue_id_is_rejected() -> None:
    queue = BoundedPriorityQueue[str]()
    job = QueueJob("same", "u1", "analyze", "payload")
    queue.enqueue(job)
    with pytest.raises(ValueError, match="duplicate_queue_job_id"):
        queue.enqueue(job)


def test_cache_fingerprint_is_stable_and_ttl_expires() -> None:
    cache = SemanticResultCache(ttl_seconds=10, max_entries=2)
    first = cache.fingerprint(operation="summary", material={"b": 2, "a": 1})
    second = cache.fingerprint(operation="summary", material={"a": 1, "b": 2})
    assert first == second

    cache.put(first, {"safe": True}, now=0)
    assert cache.get(first, now=9) == {"safe": True}
    assert cache.get(first, now=10) is None


def test_retry_only_retries_declared_transient_errors() -> None:
    calls = []
    sleeps = []

    def work() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise TimeoutError("transient")
        return "ok"

    result = execute_with_retry(
        work,
        policy=RetryPolicy(max_attempts=3, base_delay_seconds=1, max_delay_seconds=10),
        retryable=lambda exc: isinstance(exc, TimeoutError),
        sleep=sleeps.append,
    )

    assert result == "ok"
    assert len(calls) == 3
    assert sleeps == [1, 2]


def test_non_retryable_error_fails_immediately() -> None:
    calls = []

    def work() -> None:
        calls.append(1)
        raise ValueError("bad request")

    with pytest.raises(ValueError, match="bad request"):
        execute_with_retry(
            work,
            policy=RetryPolicy(max_attempts=3),
            retryable=lambda exc: isinstance(exc, TimeoutError),
            sleep=lambda _: None,
        )

    assert len(calls) == 1
