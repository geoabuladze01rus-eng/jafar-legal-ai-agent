from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryJob:
    id: str
    storage_path: str
    attempts: int


class SupabaseRecoveryQueue:
    """Atomic queue adapter for production recovery workers."""

    def __init__(self, client: object) -> None:
        self.client = client

    def enqueue_due(self, *, limit: int = 10) -> int:
        response = self.client.rpc(
            "enqueue_due_document_recovery", {"p_limit": max(1, min(limit, 100))}
        ).execute()
        return int(response.data or 0)

    def claim(self, *, worker_id: str, limit: int = 5) -> list[RecoveryJob]:
        response = self.client.rpc(
            "claim_document_recovery_jobs",
            {"p_worker_id": worker_id, "p_limit": max(1, min(limit, 50))},
        ).execute()
        return [
            RecoveryJob(id=row["id"], storage_path=row["storage_path"], attempts=int(row["attempts"]))
            for row in (response.data or [])
        ]

    def finish(self, *, job_id: str, success: bool, error: str | None = None) -> None:
        self.client.rpc(
            "finish_document_recovery_job",
            {"p_id": job_id, "p_success": success, "p_error": error},
        ).execute()
