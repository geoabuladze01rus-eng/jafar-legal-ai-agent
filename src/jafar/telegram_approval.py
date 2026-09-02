from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .action_approval import ActionRequest, LegalActionApprovalEngine


def _now() -> str:
    return datetime.now(UTC).isoformat()


def canonical_payload_hash(
    *, kind: str, chat_id: str, payload: dict[str, Any], scheduled_for: str | None
) -> str:
    body = json.dumps(
        {"kind": kind, "chat_id": chat_id, "payload": payload, "scheduled_for": scheduled_for},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


@dataclass(frozen=True, slots=True)
class TelegramApprovalRecord:
    approval_id: str
    kind: str
    chat_id: str
    payload: dict[str, Any]
    scheduled_for: str | None
    payload_hash: str
    state: str
    requested_by: str
    approved_by: str | None
    schedule_id: str | None
    message_id: int | None


class TelegramApprovalStore:
    """Durable adapter binding Telegram side effects to central JAFAR approval semantics.

    The RC's central approval engine is stateless, so this adapter persists the exact Telegram
    payload and a deterministic SHA-256 binding. Execution accepts only approval_id, never a
    replacement payload, preventing silent mutation after approval. Manual uncertain-delivery
    reconciliation is append-only audited and never re-runs the external handler.
    """

    def __init__(self, path: str | Path) -> None:
        db_path = Path(path).expanduser()
        if db_path.exists() and db_path.is_symlink():
            raise RuntimeError("telegram_approval_db_must_not_be_symlink")
        self.path = str(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("""CREATE TABLE IF NOT EXISTS telegram_publication_approvals (
                approval_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                scheduled_for TEXT,
                payload_hash TEXT NOT NULL,
                state TEXT NOT NULL,
                requested_by TEXT NOT NULL,
                approved_by TEXT,
                schedule_id TEXT,
                message_id INTEGER,
                created_at TEXT NOT NULL,
                approved_at TEXT,
                updated_at TEXT NOT NULL
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS telegram_approval_reconciliation (
                reconciliation_id TEXT PRIMARY KEY,
                approval_id TEXT NOT NULL,
                operator TEXT NOT NULL,
                confirmed_executed INTEGER NOT NULL,
                message_id INTEGER,
                evidence_note TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""")
            con.execute(
                "CREATE INDEX IF NOT EXISTS telegram_approval_reconciliation_by_approval "
                "ON telegram_approval_reconciliation(approval_id, created_at)"
            )
        self._harden_permissions()
        self._engine = LegalActionApprovalEngine()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=5.0)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=5000")
        return con

    def _harden_permissions(self) -> None:
        if os.name != "posix":
            return
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(f"{self.path}{suffix}")
            if candidate.is_symlink():
                raise RuntimeError("telegram_approval_sidecar_must_not_be_symlink")
            if candidate.exists():
                candidate.chmod(0o600)

    def create(
        self,
        *,
        kind: str,
        chat_id: str,
        payload: dict[str, Any],
        scheduled_for: str | None,
        requested_by: str,
    ) -> TelegramApprovalRecord:
        approval_id = str(uuid4())
        payload_hash = canonical_payload_hash(
            kind=kind, chat_id=chat_id, payload=payload, scheduled_for=scheduled_for
        )
        request = self._engine.propose(
            action_id=approval_id,
            action_type=f"telegram_{kind}",
            description="Owner approval required for Telegram publication",
        )
        now = _now()
        with self._connect() as con:
            con.execute(
                "INSERT INTO telegram_publication_approvals VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, NULL, ?)",
                (
                    approval_id,
                    kind,
                    chat_id,
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    scheduled_for,
                    payload_hash,
                    request.state.value,
                    requested_by,
                    now,
                    now,
                ),
            )
        self._harden_permissions()
        return self.get(approval_id)

    def get(self, approval_id: str) -> TelegramApprovalRecord:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM telegram_publication_approvals WHERE approval_id=?", (approval_id,)
            ).fetchone()
        if row is None:
            raise KeyError(approval_id)
        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            raise RuntimeError("telegram_approval_payload_invalid")
        expected = canonical_payload_hash(
            kind=row["kind"],
            chat_id=row["chat_id"],
            payload=payload,
            scheduled_for=row["scheduled_for"],
        )
        if expected != row["payload_hash"]:
            raise RuntimeError("telegram_approval_payload_mismatch")
        return TelegramApprovalRecord(
            approval_id=row["approval_id"],
            kind=row["kind"],
            chat_id=row["chat_id"],
            payload=payload,
            scheduled_for=row["scheduled_for"],
            payload_hash=row["payload_hash"],
            state=row["state"],
            requested_by=row["requested_by"],
            approved_by=row["approved_by"],
            schedule_id=row["schedule_id"],
            message_id=row["message_id"],
        )

    def approve(self, approval_id: str, *, approver: str) -> TelegramApprovalRecord:
        record = self.get(approval_id)
        if record.state != "proposed":
            raise ValueError(f"approval cannot transition from state {record.state}")
        request = ActionRequest(
            action_id=record.approval_id,
            action_type=f"telegram_{record.kind}",
            description="Owner approval required for Telegram publication",
        )
        decision = self._engine.approve(request, approver)
        now = _now()
        with self._connect() as con:
            changed = con.execute(
                "UPDATE telegram_publication_approvals "
                "SET state='approved', approved_by=?, approved_at=?, updated_at=? "
                "WHERE approval_id=? AND state='proposed'",
                (decision["approved_by"], now, now, approval_id),
            ).rowcount
        self._harden_permissions()
        if not changed:
            raise RuntimeError("telegram_approval_state_mismatch")
        return self.get(approval_id)

    def mark_scheduled(self, approval_id: str, *, schedule_id: str) -> TelegramApprovalRecord:
        with self._connect() as con:
            changed = con.execute(
                "UPDATE telegram_publication_approvals "
                "SET state='executed', schedule_id=?, updated_at=? "
                "WHERE approval_id=? AND state='approved'",
                (schedule_id, _now(), approval_id),
            ).rowcount
        self._harden_permissions()
        if not changed:
            raise RuntimeError("telegram_approval_execution_state_mismatch")
        return self.get(approval_id)

    def mark_published(
        self, approval_id: str, *, message_id: int | None
    ) -> TelegramApprovalRecord:
        with self._connect() as con:
            changed = con.execute(
                "UPDATE telegram_publication_approvals "
                "SET state='executed', message_id=?, updated_at=? "
                "WHERE approval_id=? AND state='approved'",
                (message_id, _now(), approval_id),
            ).rowcount
        self._harden_permissions()
        if not changed:
            raise RuntimeError("telegram_approval_execution_state_mismatch")
        return self.get(approval_id)

    def mark_delivery_uncertain(self, approval_id: str) -> TelegramApprovalRecord:
        with self._connect() as con:
            changed = con.execute(
                "UPDATE telegram_publication_approvals "
                "SET state='delivery_uncertain', updated_at=? "
                "WHERE approval_id=? AND state='approved'",
                (_now(), approval_id),
            ).rowcount
        self._harden_permissions()
        if not changed:
            raise RuntimeError("telegram_approval_execution_state_mismatch")
        return self.get(approval_id)

    def reconcile_uncertain(
        self,
        approval_id: str,
        *,
        operator: str,
        confirmed_executed: bool,
        evidence_note: str,
        message_id: int | None = None,
    ) -> TelegramApprovalRecord:
        record = self.get(approval_id)
        operator = operator.strip()
        evidence_note = evidence_note.strip()
        if record.state != "delivery_uncertain":
            raise ValueError("only delivery_uncertain approvals can be reconciled")
        if not operator:
            raise ValueError("reconciliation operator is required")
        if not evidence_note:
            raise ValueError("reconciliation evidence note is required")
        if len(evidence_note) > 1000:
            raise ValueError("reconciliation evidence note exceeds 1000 characters")
        if confirmed_executed and message_id is None:
            raise ValueError("confirmed executed reconciliation requires message_id")
        if message_id is not None and (isinstance(message_id, bool) or message_id <= 0):
            raise ValueError("message_id must be a positive integer")

        new_state = "executed" if confirmed_executed else "approved"
        reconciliation_id = str(uuid4())
        now = _now()
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            changed = con.execute(
                "UPDATE telegram_publication_approvals "
                "SET state=?, message_id=?, updated_at=? "
                "WHERE approval_id=? AND state='delivery_uncertain'",
                (
                    new_state,
                    message_id if confirmed_executed else None,
                    now,
                    approval_id,
                ),
            ).rowcount
            if not changed:
                raise RuntimeError("telegram_approval_reconciliation_state_mismatch")
            con.execute(
                "INSERT INTO telegram_approval_reconciliation VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    reconciliation_id,
                    approval_id,
                    operator,
                    1 if confirmed_executed else 0,
                    message_id,
                    evidence_note,
                    now,
                ),
            )
        self._harden_permissions()
        return self.get(approval_id)

    def reconciliation_history(self, approval_id: str) -> list[dict[str, Any]]:
        self.get(approval_id)
        with self._connect() as con:
            rows = con.execute(
                "SELECT reconciliation_id, operator, confirmed_executed, message_id, "
                "evidence_note, created_at FROM telegram_approval_reconciliation "
                "WHERE approval_id=? ORDER BY created_at",
                (approval_id,),
            ).fetchall()
        return [
            {
                "reconciliation_id": row["reconciliation_id"],
                "operator": row["operator"],
                "confirmed_executed": bool(row["confirmed_executed"]),
                "message_id": row["message_id"],
                "evidence_note": row["evidence_note"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def list_recent(self, limit: int = 20) -> list[TelegramApprovalRecord]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        with self._connect() as con:
            rows = con.execute(
                "SELECT approval_id FROM telegram_publication_approvals "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self.get(str(row["approval_id"])) for row in rows]
