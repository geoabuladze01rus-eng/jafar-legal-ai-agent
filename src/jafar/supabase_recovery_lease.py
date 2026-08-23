from __future__ import annotations


class SupabaseRecoveryLeaseStore:
    def __init__(self, client: object) -> None:
        self.client = client

    def heartbeat(self, *, job_id: str, worker_id: str) -> bool:
        response = self.client.rpc(
            "heartbeat_recovery_job",
            {"p_id": job_id, "p_worker_id": worker_id, "p_lease_seconds": 300},
        ).execute()
        return bool(response.data)

    def requeue_expired(self, *, lease_seconds: int = 300, limit: int = 50) -> int:
        response = self.client.rpc(
            "requeue_expired_recovery_jobs", {"p_limit": max(1, min(limit, 100))}
        ).execute()
        return int(response.data or 0)
