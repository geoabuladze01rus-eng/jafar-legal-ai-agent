from __future__ import annotations

from dataclasses import dataclass

from jafar.recovery_worker_runtime import RecoveryWorkerConfig, RecoveryWorkerRuntime
from jafar.supabase_recovery_queue import RecoveryJob, SupabaseRecoveryQueue


@dataclass
class Result:
    data: object


class FakeRpc:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return Result(self.result)


class FakeClient:
    def __init__(self):
        self.calls = []

    def rpc(self, name, args):
        self.calls.append((name, args))
        if name == "claim_document_recovery_jobs":
            return FakeRpc([{"id": "job-1", "storage_path": "m/doc.pdf", "attempts": 2}])
        return FakeRpc(None)


def test_claim_passes_worker_identity_and_finish_is_fenced():
    client = FakeClient()
    queue = SupabaseRecoveryQueue(client)
    job = queue.claim(worker_id="worker-a", limit=1)[0]
    queue.finish(job_id=job.id, worker_id="worker-a", success=True)

    assert client.calls[0] == (
        "claim_document_recovery_jobs",
        {"p_worker_id": "worker-a", "p_limit": 1},
    )
    assert client.calls[1] == (
        "finish_document_recovery_job",
        {"p_id": "job-1", "p_worker_id": "worker-a", "p_success": True, "p_error": None},
    )


def test_runtime_uses_same_worker_identity_for_job_completion():
    client = FakeClient()
    queue = SupabaseRecoveryQueue(client)

    class Executor:
        def retry(self, *, storage_path: str):
            assert storage_path == "m/doc.pdf"

    runtime = RecoveryWorkerRuntime(
        queue, Executor(), RecoveryWorkerConfig(worker_id="worker-a")
    )
    runtime._run_job(RecoveryJob("job-1", "m/doc.pdf", 2))

    assert client.calls[-1][0] == "finish_document_recovery_job"
    assert client.calls[-1][1]["p_worker_id"] == "worker-a"
