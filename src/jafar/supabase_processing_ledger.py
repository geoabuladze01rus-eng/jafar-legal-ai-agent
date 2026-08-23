from __future__ import annotations

from typing import Protocol

from .idempotency import ProcessingLedger


class SupabaseRpcClient(Protocol):
    """Minimal RPC boundary; concrete Supabase SDK stays outside Jafar Core."""

    def rpc(self, function_name: str, params: dict) -> object: ...


class SupabaseProcessingLedger(ProcessingLedger):
    """Production ledger backed by atomic PostgreSQL claim/complete functions."""

    def __init__(self, client: SupabaseRpcClient, *, sender: str, subject: str, received_at: str) -> None:
        self.client = client
        self.sender = sender
        self.subject = subject
        self.received_at = received_at

    def has_processed(self, message_id: str) -> bool:
        result = self.client.rpc("claim_email_processing", {
            "p_message_id": message_id,
            "p_sender": self.sender,
            "p_subject": self.subject,
            "p_received_at": self.received_at,
        })
        return not bool(result)

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
