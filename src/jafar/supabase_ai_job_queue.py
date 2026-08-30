from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ai_job_payload_policy import validate_durable_ai_job_payload


@dataclass(frozen=True, slots=True)
class AIJob:
    id: str
    owner_id: str
    operation: str
    payload: dict[str, Any]
    priority: int
    attempts: int
    max_attempts: int


class SupabaseAIJobQueue:
    """Owner-scoped service-role adapter for the durable production AI queue."""

    def __init__(self, client: object, owner_id: str) -> None:
        if not owner_id.strip():
            raise ValueError("ai_queue_owner_id_required")
        self.client = client
        self.owner_id = owner_id.strip()

    def enqueue(
        self,
        *,
        job_id: str,
        owner_id: str,
        operation: str,
        payload: dict[str, Any],
        priority: int = 100,
        max_attempts: int = 3,
    ) -> None:
        if not job_id.strip() or not owner_id.strip() or not operation.strip():
            raise ValueError("ai_job_identity_required")
        if owner_id.strip() != self.owner_id:
            raise PermissionError("ai_job_owner_mismatch")
        validate_durable_ai_job_payload(payload)
        if not 1 <= max_attempts <= 20:
            raise ValueError("ai_job_max_attempts_invalid")

        self.client.table("ai_jobs").insert(
            {
                "id": job_id,
                "owner_id": self.owner_id,
                "operation": operation,
                "payload": payload,
                "priority": int(priority),
                "max_attempts": int(max_attempts),
            }
        ).execute()

    def claim(self, *, worker_id: str, limit: int = 5) -> list[AIJob]:
        if not worker_id.strip():
            raise ValueError("ai_worker_id_required")
        response = self.client.rpc(
            "claim_ai_jobs",
            {
                "p_owner_id": self.owner_id,
                "p_worker_id": worker_id.strip(),
                "p_limit": max(1, min(int(limit), 50)),
            },
        ).execute()
        jobs = [self._hydrate(row) for row in (response.data or [])]
        if any(job.owner_id != self.owner_id for job in jobs):
            raise RuntimeError("ai_job_cross_owner_response")
        return jobs

    def mark_dispatched(self, *, job_id: str, worker_id: str) -> AIJob:
        """Record the point after which automatic replay is unsafe."""
        if not job_id.strip() or not worker_id.strip():
            raise ValueError("ai_job_and_worker_required")
        response = self.client.rpc(
            "mark_ai_job_dispatched",
            {
                "p_owner_id": self.owner_id,
                "p_id": job_id,
                "p_worker_id": worker_id.strip(),
            },
        ).execute()
        job = self._hydrate_single(response.data, "ai_job_dispatch_response_invalid")
        self._require_owner(job)
        return job

    def reclaim_stale_undispatched(self, *, stale_seconds: int = 300, limit: int = 50) -> int:
        """Recover only owner-scoped claims for which provider dispatch provably never began."""
        stale = max(60, min(int(stale_seconds), 86400))
        bounded_limit = max(1, min(int(limit), 500))
        response = self.client.rpc(
            "reclaim_stale_undispatched_ai_jobs",
            {
                "p_owner_id": self.owner_id,
                "p_stale_seconds": stale,
                "p_limit": bounded_limit,
            },
        ).execute()
        value = response.data
        if isinstance(value, list):
            value = value[0] if value else None
        if isinstance(value, bool) or not isinstance(value, int):
            raise RuntimeError("ai_job_reclaim_response_invalid")  # noqa: TRY004
        return value

    def finish(
        self,
        *,
        job_id: str,
        worker_id: str,
        success: bool,
        error_code: str | None = None,
        retry_after_seconds: int = 0,
    ) -> AIJob:
        if not job_id.strip() or not worker_id.strip():
            raise ValueError("ai_job_and_worker_required")
        safe_error = None if error_code is None else error_code.strip()[:96]
        response = self.client.rpc(
            "finish_ai_job",
            {
                "p_owner_id": self.owner_id,
                "p_id": job_id,
                "p_worker_id": worker_id.strip(),
                "p_success": bool(success),
                "p_error_code": safe_error,
                "p_retry_after_seconds": max(0, min(int(retry_after_seconds), 86400)),
            },
        ).execute()
        job = self._hydrate_single(response.data, "ai_job_finish_response_invalid")
        self._require_owner(job)
        return job

    def _require_owner(self, job: AIJob) -> None:
        if job.owner_id != self.owner_id:
            raise RuntimeError("ai_job_cross_owner_response")

    @classmethod
    def _hydrate_single(cls, data: Any, error_code: str) -> AIJob:
        row = data
        if isinstance(row, list):
            row = row[0] if row else None
        if not isinstance(row, dict):
            raise RuntimeError(error_code)  # noqa: TRY004
        return cls._hydrate(row)

    @staticmethod
    def _hydrate(row: dict[str, Any]) -> AIJob:
        payload = row.get("payload")
        if not isinstance(payload, dict):
            raise RuntimeError("ai_job_payload_invalid")  # noqa: TRY004
        return AIJob(
            id=str(row["id"]),
            owner_id=str(row["owner_id"]),
            operation=str(row["operation"]),
            payload=payload,
            priority=int(row.get("priority", 100)),
            attempts=int(row.get("attempts", 0)),
            max_attempts=int(row.get("max_attempts", 3)),
        )
