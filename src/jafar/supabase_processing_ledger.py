from __future__ import annotations

from typing import Protocol

from .idempotency import ProcessingLedger


class SupabaseRpcClient(Protocol):
    """Minimal RPC boundary; concrete Supabase SDK stays outside Jafar Core."""

    def rpc(self, function_name: str, params: dict) -> object: ...


class SupabaseProcessingLedger(ProcessingLedger):
    """Production ledger backed by atomic PostgreSQL claim/complete functions."""

    def __init__(self, client: SupabaseRpcClient) -> None:
        self.client = client

    def claim(self, message_id: str, *, sender: str, subject: str, received_at: str) -> bool:
        result = self.client.rpc("claim_email_processing", {
            "p_message_id": message_id,
            "p_sender": sender,
            "p_subject": subject,
            "p_received_at": received_at,
        })
        return bool(result)

    def mark_processed(self, message_id: str) -> None:
        self.client.rpc("complete_email_processing", {
            "p_message_id": message_id,
            "p_failed": False,
        })

    def mark_failed(self, message_id: str) -> None:
        self.client.rpc("complete_email_processing", {
            "p_message_id": message_id,
            "p_failed": True,
        })
