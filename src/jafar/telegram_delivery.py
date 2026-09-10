from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Protocol

from .audit_trail import AuditEvent, AuditTrail


class DeliveryLedgerState(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    SENT = "sent"
    UNCERTAIN = "uncertain"
    FAILED = "failed"


_SECRET_KEY_RE = re.compile(r"token|secret|password|authorization|api[_-]?key", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class DeliveryRecord:
    publication_id: str
    payload_hash: str
    state: DeliveryLedgerState
    claimed_at: datetime
    updated_at: datetime
    telegram_message_id: int | None = None
    error_code: str | None = None
    reconciliation_note: str | None = None


class PublicationDeliveryLedger(Protocol):
    def claim(self, publication_id: str, *, payload_hash: str) -> bool: ...
    def mark_sent(self, publication_id: str, *, telegram_message_id: int) -> None: ...
    def mark_failed(self, publication_id: str, *, error_code: str) -> None: ...
    def mark_uncertain(self, publication_id: str, *, note: str) -> None: ...
    def release_failed_for_retry(self, publication_id: str) -> bool: ...
    def reconcile_sent(
        self,
        publication_id: str,
        *,
        telegram_message_id: int,
        note: str,
    ) -> None: ...
    def get(self, publication_id: str) -> DeliveryRecord | None: ...


class InMemoryPublicationDeliveryLedger:
    """Reference delivery ledger with fail-closed retry semantics.

    CLAIMED and UNCERTAIN records cannot be re-claimed. A definite FAILED record
    also stays blocked until an explicit operator retry resets it to PENDING.
    SENT can never be re-claimed. Once a Publication ID exists, changing its
    payload hash is not a retry: it requires a new Publication ID.
    """

    def __init__(self) -> None:
        self._records: dict[str, DeliveryRecord] = {}

    def claim(self, publication_id: str, *, payload_hash: str) -> bool:
        existing = self._records.get(publication_id)
        if existing is not None:
            if existing.payload_hash != payload_hash:
                return False
            if existing.state is not DeliveryLedgerState.PENDING:
                return False
        now = datetime.now(timezone.utc)
        self._records[publication_id] = DeliveryRecord(
            publication_id=publication_id,
            payload_hash=payload_hash,
            state=DeliveryLedgerState.CLAIMED,
            claimed_at=now,
            updated_at=now,
        )
        return True

    def mark_sent(self, publication_id: str, *, telegram_message_id: int) -> None:
        record = self._require(publication_id)
        if record.state is not DeliveryLedgerState.CLAIMED:
            raise RuntimeError(f"cannot mark {record.state.value} delivery as sent")
        self._records[publication_id] = replace(
            record,
            state=DeliveryLedgerState.SENT,
            telegram_message_id=telegram_message_id,
            updated_at=datetime.now(timezone.utc),
            error_code=None,
        )

    def mark_failed(self, publication_id: str, *, error_code: str) -> None:
        record = self._require(publication_id)
        if record.state is not DeliveryLedgerState.CLAIMED:
            raise RuntimeError(f"cannot mark {record.state.value} delivery as failed")
        self._records[publication_id] = replace(
            record,
            state=DeliveryLedgerState.FAILED,
            updated_at=datetime.now(timezone.utc),
            error_code=_safe_error_code(error_code),
        )

    def mark_uncertain(self, publication_id: str, *, note: str) -> None:
        record = self._require(publication_id)
        if record.state is not DeliveryLedgerState.CLAIMED:
            raise RuntimeError(f"cannot mark {record.state.value} delivery as uncertain")
        self._records[publication_id] = replace(
            record,
            state=DeliveryLedgerState.UNCERTAIN,
            updated_at=datetime.now(timezone.utc),
            reconciliation_note=_sanitize_text(note),
        )

    def release_failed_for_retry(self, publication_id: str) -> bool:
        record = self._require(publication_id)
        if record.state is not DeliveryLedgerState.FAILED:
            return False
        self._records[publication_id] = replace(
            record,
            state=DeliveryLedgerState.PENDING,
            updated_at=datetime.now(timezone.utc),
            error_code=None,
        )
        return True

    def reconcile_sent(
        self,
        publication_id: str,
        *,
        telegram_message_id: int,
        note: str,
    ) -> None:
        record = self._require(publication_id)
        if record.state is not DeliveryLedgerState.UNCERTAIN:
            raise RuntimeError("reconciliation is only valid for uncertain delivery")
        self._records[publication_id] = replace(
            record,
            state=DeliveryLedgerState.SENT,
            telegram_message_id=telegram_message_id,
            updated_at=datetime.now(timezone.utc),
            reconciliation_note=_sanitize_text(note),
        )

    def get(self, publication_id: str) -> DeliveryRecord | None:
        return self._records.get(publication_id)

    def _require(self, publication_id: str) -> DeliveryRecord:
        record = self._records.get(publication_id)
        if record is None:
            raise KeyError(publication_id)
        return record


class PublicationAudit:
    """Append-only publication audit wrapper with recursive secret redaction."""

    def __init__(self, trail: AuditTrail, *, actor: str = "jafar.telegram") -> None:
        self.trail = trail
        self.actor = actor

    def record(
        self,
        *,
        publication_id: str,
        event_type: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            actor=self.actor,
            request_id=publication_id,
            action="telegram_publication",
            status=status,
            metadata=sanitize_metadata(metadata or {}),
        )
        return self.trail.record(event)


def payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sanitize_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            if _SECRET_KEY_RE.search(str(key)):
                clean[str(key)] = "[REDACTED]"
            else:
                clean[str(key)] = sanitize_metadata(item)
        return clean
    if isinstance(value, list):
        return [sanitize_metadata(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_metadata(item) for item in value)
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def _safe_error_code(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.:-]+", "_", value.strip())
    return normalized[:120] or "unknown_error"


def _sanitize_text(value: str) -> str:
    # Remove common bearer/bot token shapes from free text without retaining the secret.
    value = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", value)
    value = re.sub(
        r"\b\d{6,12}:[A-Za-z0-9_-]{20,}\b",
        "[TELEGRAM TOKEN REDACTED]",
        value,
    )
    return value[:1000]
