from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


def parse_schedule_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            "scheduled_for must be ISO-8601 with timezone, e.g. 2026-08-29T09:00:00+03:00"
        ) from exc
    if parsed.tzinfo is None:
        raise ValueError("scheduled_for must include a timezone offset")
    parsed = parsed.astimezone(UTC)
    if parsed <= utc_now():
        raise ValueError("scheduled_for must be in the future")
    return parsed


def _safe_delivery_error(exc: Exception) -> str:
    """Persist a low-information error code rather than exception text or Telegram payloads."""
    if isinstance(exc, PermissionError):
        return "delivery_policy_denied"
    if isinstance(exc, ValueError):
        return "delivery_invalid_payload"
    if isinstance(exc, TimeoutError):
        return "delivery_timeout"
    name = re.sub(r"[^a-z0-9]+", "_", type(exc).__name__.casefold()).strip("_")
    return f"delivery_{name or 'failure'}"[:96]


@dataclass(frozen=True)
class ScheduledItem:
    id: str
    kind: str
    chat_id: str
    payload: dict[str, Any]
    scheduled_for: datetime
    status: str
    idempotency_key: str
    recurrence_seconds: int | None
    message_id: int | None
    error: str | None


class TelegramScheduleStore:
    """SQLite state machine. `sending` jobs are never automatically retried after a crash."""

    def __init__(self, path: str | Path) -> None:
        db_path = Path(path).expanduser()
        if db_path.exists() and db_path.is_symlink():
            raise RuntimeError("telegram_scheduler_db_must_not_be_symlink")
        self.path = str(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._harden_permissions()

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
            if candidate.exists():
                if candidate.is_symlink():
                    raise RuntimeError("telegram_scheduler_sidecar_must_not_be_symlink")
                candidate.chmod(0o600)

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("""CREATE TABLE IF NOT EXISTS telegram_scheduled_items (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, chat_id TEXT NOT NULL, payload_json TEXT NOT NULL,
                scheduled_for TEXT NOT NULL, status TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE,
                recurrence_seconds INTEGER, message_id INTEGER, error TEXT, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, parent_id TEXT
            )""")
            con.execute(
                "CREATE INDEX IF NOT EXISTS telegram_scheduled_due ON telegram_scheduled_items(status, scheduled_for)"
            )
            con.execute(
                "UPDATE telegram_scheduled_items SET status='failed', error='interrupted_before_delivery_confirmation', updated_at=? WHERE status='sending'",
                (utc_now().isoformat(),),
            )
        self._harden_permissions()

    def schedule(
        self,
        *,
        kind: str,
        chat_id: str,
        payload: dict[str, Any],
        scheduled_for: datetime,
        idempotency_key: str,
        recurrence_seconds: int | None = None,
        parent_id: str | None = None,
    ) -> ScheduledItem:
        if recurrence_seconds is not None and recurrence_seconds < 60:
            raise ValueError("recurrence_seconds must be at least 60")
        item_id, now = str(uuid4()), utc_now().isoformat()
        normalized_time = scheduled_for.astimezone(UTC)
        try:
            with self._connect() as con:
                con.execute(
                    "INSERT INTO telegram_scheduled_items VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, NULL, NULL, ?, ?, 0, ?)",
                    (
                        item_id,
                        kind,
                        chat_id,
                        json.dumps(payload, sort_keys=True, separators=(",", ":")),
                        normalized_time.isoformat(),
                        idempotency_key,
                        recurrence_seconds,
                        now,
                        now,
                        parent_id,
                    ),
                )
        except sqlite3.IntegrityError:
            existing = self.by_idempotency_key(idempotency_key)
            if (
                existing.kind != kind
                or existing.chat_id != chat_id
                or existing.payload != payload
                or existing.scheduled_for != normalized_time
                or existing.recurrence_seconds != recurrence_seconds
            ):
                raise ValueError("idempotency_key_conflict") from None
            return existing
        finally:
            self._harden_permissions()
        return self.get(item_id)

    def by_idempotency_key(self, key: str) -> ScheduledItem:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM telegram_scheduled_items WHERE idempotency_key=?", (key,)
            ).fetchone()
        if row is None:
            raise KeyError(key)
        return self._item(row)

    def get(self, item_id: str) -> ScheduledItem:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM telegram_scheduled_items WHERE id=?", (item_id,)
            ).fetchone()
        if row is None:
            raise KeyError(item_id)
        return self._item(row)

    def list(self, statuses: tuple[str, ...] = ("pending", "sending", "failed")) -> list[ScheduledItem]:
        if not statuses:
            return []
        marks = ",".join("?" for _ in statuses)
        with self._connect() as con:
            rows = con.execute(
                f"SELECT * FROM telegram_scheduled_items WHERE status IN ({marks}) ORDER BY scheduled_for",
                statuses,
            ).fetchall()
        return [self._item(row) for row in rows]

    def cancel(self, item_id: str) -> ScheduledItem:
        with self._connect() as con:
            changed = con.execute(
                "UPDATE telegram_scheduled_items SET status='cancelled', updated_at=? WHERE id=? AND status='pending'",
                (utc_now().isoformat(), item_id),
            ).rowcount
        self._harden_permissions()
        if not changed:
            item = self.get(item_id)
            if item.status == "pending":
                raise KeyError(item_id)
            raise ValueError(f"scheduled item cannot be cancelled from status {item.status}")
        return self.get(item_id)

    def claim_due(self, now: datetime | None = None) -> list[ScheduledItem]:
        current = (now or utc_now()).astimezone(UTC).isoformat()
        claimed: list[str] = []
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            rows = con.execute(
                "SELECT id FROM telegram_scheduled_items WHERE status='pending' AND scheduled_for<=? ORDER BY scheduled_for, id",
                (current,),
            ).fetchall()
            for row in rows:
                if con.execute(
                    "UPDATE telegram_scheduled_items SET status='sending', attempts=attempts+1, updated_at=? WHERE id=? AND status='pending'",
                    (current, row["id"]),
                ).rowcount:
                    claimed.append(row["id"])
        self._harden_permissions()
        return [self.get(item_id) for item_id in claimed]

    def finish(self, item: ScheduledItem, *, message_id: int | None = None, error: str | None = None) -> None:
        status = "failed" if error else "sent"
        with self._connect() as con:
            changed = con.execute(
                "UPDATE telegram_scheduled_items SET status=?, message_id=?, error=?, updated_at=? WHERE id=? AND status='sending'",
                (status, message_id, error, utc_now().isoformat(), item.id),
            ).rowcount
        self._harden_permissions()
        if not changed:
            raise RuntimeError("scheduled_item_finish_state_mismatch")
        if not error and item.recurrence_seconds:
            next_time = item.scheduled_for + timedelta(seconds=item.recurrence_seconds)
            while next_time <= utc_now():
                next_time += timedelta(seconds=item.recurrence_seconds)
            self.schedule(
                kind=item.kind,
                chat_id=item.chat_id,
                payload=item.payload,
                scheduled_for=next_time,
                idempotency_key=f"{item.idempotency_key}:{next_time.isoformat()}",
                recurrence_seconds=item.recurrence_seconds,
                parent_id=item.id,
            )

    @staticmethod
    def _item(row: sqlite3.Row) -> ScheduledItem:
        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            raise RuntimeError("scheduled_item_payload_invalid")
        return ScheduledItem(
            row["id"], row["kind"], row["chat_id"], payload,
            datetime.fromisoformat(row["scheduled_for"]), row["status"],
            row["idempotency_key"], row["recurrence_seconds"], row["message_id"], row["error"]
        )


class TelegramScheduler:
    def __init__(self, store: TelegramScheduleStore, deliver: Callable[[ScheduledItem], Awaitable[int | None]]) -> None:
        self.store, self.deliver = store, deliver

    async def run_due(self, now: datetime | None = None) -> int:
        items = self.store.claim_due(now)
        for item in items:
            try:
                message_id = await self.deliver(item)
            except Exception as exc:  # noqa: BLE001
                self.store.finish(item, error=_safe_delivery_error(exc))
            else:
                self.store.finish(item, message_id=message_id)
        return len(items)

    async def serve(self, stop: asyncio.Event, interval_seconds: float = 5.0) -> None:
        if interval_seconds < 0.25 or interval_seconds > 300:
            raise ValueError("scheduler interval_seconds must be between 0.25 and 300")
        while not stop.is_set():
            await self.run_due()
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except TimeoutError:
                pass
