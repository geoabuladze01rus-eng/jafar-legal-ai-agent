from __future__ import annotations

import pytest

from jafar.ai_queue_runtime import LocalAIJobQueue, build_ai_queue
from jafar.config import Settings


def test_development_uses_bounded_local_queue() -> None:
    queue = build_ai_queue(
        Settings(
            environment="development",
            ai_queue_backend="memory",
            ai_queue_max_size=2,
            ai_queue_max_per_user=1,
        )
    )
    assert isinstance(queue, LocalAIJobQueue)

    queue.enqueue(
        job_id="job-1",
        owner_id="lawyer-1",
        operation="analysis",
        payload={"matter_id": "matter-1"},
    )
    with pytest.raises(RuntimeError, match="ai_queue_user_limit"):
        queue.enqueue(
            job_id="job-2",
            owner_id="lawyer-1",
            operation="analysis",
            payload={"matter_id": "matter-2"},
        )


def test_production_rejects_in_memory_queue() -> None:
    with pytest.raises(RuntimeError, match="durable Supabase backend"):
        build_ai_queue(Settings(environment="production", ai_queue_backend="memory"))


def test_unknown_queue_backend_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="Unsupported AI queue backend"):
        build_ai_queue(Settings(environment="development", ai_queue_backend="redis-maybe"))


def test_local_queue_does_not_pretend_to_support_durable_retry_ledger() -> None:
    queue = LocalAIJobQueue(max_size=2, max_per_user=2)
    with pytest.raises(ValueError, match="local_ai_queue_fixed_retry_policy"):
        queue.enqueue(
            job_id="job-1",
            owner_id="lawyer-1",
            operation="analysis",
            payload={},
            max_attempts=5,
        )
