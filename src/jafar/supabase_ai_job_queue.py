from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
    """Service-role adapter for the durable production AI queue.

    The queue payload may contain privileged legal material and therefore must never be exposed
    directly to app clients. Claim/finish transitions are performed by server-only RPCs.
    """

    def __init__(self, client: object) -> None:
        self.client = client

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
        if not isinstance(payload, dict):
            raise ValueError("ai_job_payload_must_be_object")
        if not 1 <= max_attempts <= 20:
            raise ValueError("ai_job_max_attempts_invalid")

        self.client.table("ai_jobs").insert(
            {
                "id": job_id,
                "owner_id": owner_id,
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
            {"p_worker_id": worker_id.strip(), "p_limit": max(1, min(int(limit), 50))},
        ).execute()
        return [self._hydrate(row) for row in (response.data or [])]

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
                "p_id": job_id,
                "p_worker_id": worker_id.strip(),
                "p_success": bool(success),
                "p_error_code": safe_error,
                "p_retry_after_seconds": max(0, min(int(retry_after_seconds), 86400)),
            },
        ).execute()
        row = response.data
        if isinstance(row, list):
            row = row[0] if row else None
        if not isinstance(row, dict):
            raise RuntimeError("ai_job_finish_response_invalid")
        return self._hydrate(row)

    @staticmethod
    def _hydrate(row: dict[str, Any]) -> AIJob:
        payload = row.get("payload")
        if not isinstance(payload, dict):
            raise RuntimeError("ai_job_payload_invalid")
        return AIJob(
            id=str(row["id"]),
            owner_id=str(row["owner_id"]),
            operation=str(row["operation"]),
            payload=payload,
            priority=int(row.get("priority", 100)),
            attempts=int(row.get("attempts", 0)),
            max_attempts=int(row.get("max_attempts", 3)),
        )
