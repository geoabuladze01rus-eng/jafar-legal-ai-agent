from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Protocol

from .telegram_delivery import (
    DeliveryLedgerState,
    DeliveryRecord,
    PublicationDeliveryLedger,
)


_PAYLOAD_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_SECRET_TEXT_RE = re.compile(
    r"(?i)(bearer\s+[A-Za-z0-9._~+/=-]+|\b\d{6,12}:[A-Za-z0-9_-]{20,}\b)"
)


class SupabaseRpcClient(Protocol):
    def rpc(self, function_name: str, params: dict[str, Any]) -> object: ...


class SupabaseTelegramDeliveryLedger(PublicationDeliveryLedger):
    """Persistent Telegram delivery ledger backed by atomic Supabase RPC functions.

    Input validation and state parsing intentionally fail closed. In particular, an
    unknown state coming back from storage is treated as UNCERTAIN so an operator
    must reconcile it before any retry can happen.
    """

    def __init__(self, client: SupabaseRpcClient) -> None:
        self.client = client

    def claim(self, publication_id: str, *, payload_hash: str) -> bool:
        publication_id = _validate_publication_id(publication_id)
        payload_hash = _validate_payload_hash(payload_hash)
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
                "p_publication_id": _validate_publication_id(publication_id),
                "p_telegram_message_id": _validate_message_id(telegram_message_id),
            },
        )

    def mark_failed(self, publication_id: str, *, error_code: str) -> None:
        self._rpc(
            "mark_telegram_publication_failed",
            {
                "p_publication_id": _validate_publication_id(publication_id),
                "p_error_code": _safe_error_code(error_code),
            },
        )

    def mark_uncertain(self, publication_id: str, *, note: str) -> None:
        self._rpc(
            "mark_telegram_publication_uncertain",
            {
                "p_publication_id": _validate_publication_id(publication_id),
                "p_note": _sanitize_note(note),
            },
        )

    def release_failed_for_retry(self, publication_id: str) -> bool:
        data = self._rpc(
            "release_telegram_publication_failed",
            {"p_publication_id": _validate_publication_id(publication_id)},
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
                "p_publication_id": _validate_publication_id(publication_id),
                "p_telegram_message_id": _validate_message_id(telegram_message_id),
                "p_note": _sanitize_note(note),
            },
        )

    def get(self, publication_id: str) -> DeliveryRecord | None:
        publication_id = _validate_publication_id(publication_id)
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

        state = _parse_state(data.get("state"))
        message_id = _optional_int(data.get("telegram_message_id"))
        if state is DeliveryLedgerState.SENT and (message_id is None or message_id <= 0):
            # A stored SENT row without a usable Telegram ID is inconsistent. Treat
            # it as uncertain to ensure no automatic retry can duplicate a post.
            state = DeliveryLedgerState.UNCERTAIN
            message_id = None

        return DeliveryRecord(
            publication_id=str(data["publication_id"]),
            payload_hash=_validate_payload_hash(str(data["payload_hash"])),
            state=state,
            claimed_at=_parse_datetime(data["claimed_at"]),
            updated_at=_parse_datetime(data["updated_at"]),
            telegram_message_id=message_id,
            error_code=_optional_text(data.get("error_code")),
            reconciliation_note=_optional_text(data.get("reconciliation_note")),
        )

    def _rpc(self, name: str, params: dict[str, Any]) -> Any:
        call = self.client.rpc(name, params)
        execute = getattr(call, "execute", None)
        result = execute() if callable(execute) else call
        return getattr(result, "data", result)


def _validate_publication_id(value: str) -> str:
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError("publication_id must not be blank")
    if len(cleaned) > 200:
        raise ValueError("publication_id is too long")
    return cleaned


def _validate_payload_hash(value: str) -> str:
    cleaned = str(value).strip()
    if not _PAYLOAD_HASH_RE.fullmatch(cleaned):
        raise ValueError("payload_hash must be 64 lowercase hexadecimal characters")
    return cleaned


def _validate_message_id(value: int) -> int:
    message_id = int(value)
    if message_id <= 0:
        raise ValueError("telegram_message_id must be positive")
    return message_id


def _parse_state(value: Any) -> DeliveryLedgerState:
    try:
        return DeliveryLedgerState(str(value))
    except (TypeError, ValueError):
        return DeliveryLedgerState.UNCERTAIN


def _safe_error_code(value: str) -> str:
    sanitized = _sanitize_note(value)
    normalized = re.sub(r"[^A-Za-z0-9_.:-]+", "_", sanitized.strip())
    return normalized[:120] or "unknown_error"


def _sanitize_note(value: str) -> str:
    text = str(value)
    text = _SECRET_TEXT_RE.sub("[REDACTED]", text)
    return text[:1000]


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
