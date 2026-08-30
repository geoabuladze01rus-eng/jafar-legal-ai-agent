from __future__ import annotations

import pytest

from jafar.supabase_ai_job_queue import SupabaseAIJobQueue


class _Response:
    def __init__(self, data=None):
        self.data = data


_JOB = {
    "id": "job-1",
    "owner_id": "lawyer-1",
    "operation": "case_analysis",
    "payload": {"matter_id": "matter-1"},
    "priority": 10,
    "attempts": 1,
    "max_attempts": 3,
}


class _Action:
    def __init__(self, client, kind, name):
        self.client = client
        self.kind = kind
        self.name = name
        self.payload = None

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        self.client.calls.append((self.kind, self.name, self.payload))
        if self.kind == "rpc" and self.name == "claim_ai_jobs":
            return _Response([dict(_JOB)])
        if self.kind == "rpc" and self.name in {"finish_ai_job", "mark_ai_job_dispatched"}:
            return _Response(dict(_JOB))
        if self.kind == "rpc" and self.name == "reclaim_stale_undispatched_ai_jobs":
            return _Response(2)
        return _Response()


class _Client:
    def __init__(self):
        self.calls = []

    def table(self, name):
        return _Action(self, "table", name)

    def rpc(self, name, payload):
        action = _Action(self, "rpc", name)
        action.payload = payload
        return action


def _queue(client=None) -> SupabaseAIJobQueue:
    return SupabaseAIJobQueue(client or _Client(), "lawyer-1")


def test_queue_enqueues_and_claims_only_configured_owner_jobs() -> None:
    client = _Client()
    queue = _queue(client)

    queue.enqueue(
        job_id="job-1",
        owner_id="lawyer-1",
        operation="case_analysis",
        payload={"matter_id": "matter-1"},
        priority=10,
    )
    jobs = queue.claim(worker_id="worker-a", limit=500)

    assert client.calls[0][0:2] == ("table", "ai_jobs")
    assert client.calls[0][2]["owner_id"] == "lawyer-1"
    assert client.calls[1] == (
        "rpc",
        "claim_ai_jobs",
        {"p_owner_id": "lawyer-1", "p_worker_id": "worker-a", "p_limit": 50},
    )
    assert jobs[0].id == "job-1"
    assert jobs[0].attempts == 1


def test_queue_rejects_cross_owner_enqueue() -> None:
    queue = _queue()

    with pytest.raises(PermissionError, match="ai_job_owner_mismatch"):
        queue.enqueue(
            job_id="job-2",
            owner_id="lawyer-2",
            operation="case_analysis",
            payload={"matter_id": "matter-2"},
        )


def test_worker_marks_provider_dispatch_with_owner_scope() -> None:
    client = _Client()
    queue = _queue(client)

    job = queue.mark_dispatched(job_id="job-1", worker_id="worker-a")

    assert client.calls[-1] == (
        "rpc",
        "mark_ai_job_dispatched",
        {"p_owner_id": "lawyer-1", "p_id": "job-1", "p_worker_id": "worker-a"},
    )
    assert job.id == "job-1"


def test_only_stale_undispatched_claims_have_owner_scoped_automatic_recovery_path() -> None:
    client = _Client()
    queue = _queue(client)

    reclaimed = queue.reclaim_stale_undispatched(stale_seconds=1, limit=9999)

    assert reclaimed == 2
    assert client.calls[-1] == (
        "rpc",
        "reclaim_stale_undispatched_ai_jobs",
        {"p_owner_id": "lawyer-1", "p_stale_seconds": 60, "p_limit": 500},
    )


def test_finish_uses_owner_and_worker_claim_with_sanitized_retry_parameters() -> None:
    client = _Client()
    queue = _queue(client)

    job = queue.finish(
        job_id="job-1",
        worker_id="worker-a",
        success=False,
        error_code="x" * 200,
        retry_after_seconds=999999,
    )

    kind, name, payload = client.calls[-1]
    assert (kind, name) == ("rpc", "finish_ai_job")
    assert payload["p_owner_id"] == "lawyer-1"
    assert payload["p_worker_id"] == "worker-a"
    assert payload["p_retry_after_seconds"] == 86400
    assert len(payload["p_error_code"]) == 96
    assert job.owner_id == "lawyer-1"


def test_queue_rejects_missing_identity_and_non_object_payload() -> None:
    queue = _queue()

    with pytest.raises(ValueError, match="ai_job_identity_required"):
        queue.enqueue(job_id="", owner_id="lawyer-1", operation="analysis", payload={})
    with pytest.raises(ValueError, match="ai_job_payload_must_be_object"):
        queue.enqueue(
            job_id="job-1",
            owner_id="lawyer-1",
            operation="analysis",
            payload=[],  # type: ignore[arg-type]
        )


def test_queue_rejects_cross_owner_rpc_response() -> None:
    client = _Client()
    queue = _queue(client)
    original = _JOB["owner_id"]
    _JOB["owner_id"] = "lawyer-2"
    try:
        with pytest.raises(RuntimeError, match="ai_job_cross_owner_response"):
            queue.claim(worker_id="worker-a")
    finally:
        _JOB["owner_id"] = original
