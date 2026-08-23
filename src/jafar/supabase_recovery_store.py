from __future__ import annotations

from .document_recovery import RecoveryCandidate


class SupabaseRecoveryStore:
    """Atomic production claim store for scheduled document recovery."""

    def __init__(self, client: object) -> None:
        self.client = client

    def claim_due(self, *, limit: int) -> list[RecoveryCandidate]:
        response = self.client.rpc(
            "run_document_recovery_tick",
            {"p_limit": max(1, min(limit, 100))},
        ).execute()
        rows = response.data or []
        return [
            RecoveryCandidate(
                storage_path=row["storage_path"],
                retry_attempts=int(row["retry_attempts"]),
            )
            for row in rows
        ]
