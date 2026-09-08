from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from .telegram_delivery import (
    DeliveryLedgerState,
    DeliveryRecord,
    PublicationDeliveryLedger,
)


class SupabaseRpcClient(Protocol):
    def rpc(self, function_name: str, params: dict[str, Any]) -> object: ...


class SupabaseTelegramDeliveryLedger(PublicationDeliveryLedger):
    """Persistent Telegram delivery ledger backed by atomic Supabase RPC functions."""

    def __init__(self, client: SupabaseRpcClient) -> None:
        self.client = client

    def claim(self, publication_id: str, *, payload_hash: str) -> bool:
        data = self._rpc(
            "claim_telegram_publication",
            {
                "p_publication_id": publication_id,
                "p_payload_hash": payload_hash,
            },
        )
        return bool(data)

    def mark_sent(self, publication_id: str, *, telegram_message_id: int) -> None:
        self._rpc(
            "mark_telegram_publication_sent",
            {
                "p_publication_id": publication_id,
                "p_telegram_message_id": telegram_message_id,
            },
        )

    def mark_failed(self, publication_id: str, *, error_code: str) -> None:
        self._rpc(
            "mark_telegram_publication_failed",
            {
                "p_publication_id": publication_id,
                "p_error_code": error_code,
            },
        )

    def mark_uncertain(self, publication_id: str, *, note: str) -> None:
        self._rpc(
            "mark_telegram_publication_uncertain",
            {
                "p_publication_id": publication_id,
                "p_note": note,
            },
        )

    def release_failed_for_retry(self, publication_id: str) -> bool:
        data = self._rpc(
            "release_telegram_publication_failed",
            {"p_publication_id": publication_id},
        )
        return bool(data)

    def reconcile_sent(
        self,
        publication_id: str,
        *,
        telegram_message_id: int,
        note: str,
    ) -> None:
        self._rpc(
            "reconcile_telegram_publication_sent",
            {
                "p_publication_id": publication_id,
                "p_telegram_message_id": telegram_message_id,
                "p_note": note,
            },
        )

    def get(self, publication_id: str) -> DeliveryRecord | None:
        data = self._rpc(
            "get_telegram_publication_delivery",
            {"p_publication_id": publication_id},
        )
        if data in (None, {}):
            return None
        if isinstance(data, list):
            if not data:
                return None
            data = data[0]
        if not isinstance(data, dict):
            raise TypeError("Supabase returned an unexpected Telegram delivery record")
        return DeliveryRecord(
            publication_id=str(data["publication_id"]),
            payload_hash=str(data["payload_hash"]),
            state=DeliveryLedgerState(str(data["state"])),
            claimed_at=_parse_datetime(data["claimed_at"]),
            updated_at=_parse_datetime(data["updated_at"]),
            telegram_message_id=_optional_int(data.get("telegram_message_id")),
            error_code=_optional_text(data.get("error_code")),
            reconciliation_note=_optional_text(data.get("reconciliation_note")),
        )

    def _rpc(self, name: str, params: dict[str, Any]) -> Any:
        call = self.client.rpc(name, params)
        execute = getattr(call, "execute", None)
        result = execute() if callable(execute) else call
        return getattr(result, "data", result)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Supabase delivery timestamps must be timezone-aware")
    return dt


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _optional_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
