"""Desktop-only durable Matter repository with authenticated encrypted payloads."""

from __future__ import annotations

import base64
import os
import sqlite3
from uuid import uuid4
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Iterator

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .legal_models import Deadline, Matter, MatterEvent
from .matter_repository import MatterRepository
from .matters import utcnow


SCHEMA_VERSION = 1
_KEY_INFO = b"jafar-desktop-matter-storage-v1"
_CHECK_VALUE = b"jafar-desktop-storage-check-v1"


class DesktopStorageError(RuntimeError):
    """Storage cannot safely be opened; callers must not fall back to plaintext."""


def storage_key_from_environment() -> bytes:
    encoded = os.getenv("JAFAR_DESKTOP_STORAGE_KEY", "").strip()
    if not encoded:
        raise DesktopStorageError("desktop storage key is unavailable")
    try:
        master_key = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (ValueError, TypeError) as exc:
        raise DesktopStorageError("desktop storage key is invalid") from exc
    if len(master_key) != 32:
        raise DesktopStorageError("desktop storage key is invalid")
    return HKDF(algorithm=SHA256(), length=32, salt=b"JAFAR desktop storage", info=_KEY_INFO).derive(master_key)


class EncryptedSQLiteMatterRepository(MatterRepository):
    """SQLite metadata plus AES-GCM encrypted Matter/event payloads.

    SQLite's WAL and explicit transactions provide crash safety.  IDs and timestamps
    remain queryable metadata; every legal/domain field is encrypted with a distinct
    random nonce and AES-GCM additional authenticated data bound to its record ID.
    """

    def __init__(self, database_path: Path, key: bytes, lock_path: Path) -> None:
        self.database_path = database_path
        self.lock_path = lock_path
        self._cipher = AESGCM(key)
        self._mutex = RLock()
        self._lock_handle = self._acquire_lock(lock_path)
        try:
            self._connection = self._open()
            self._migrate()
        except Exception:
            self._lock_handle.close()
            raise

    @staticmethod
    def _acquire_lock(lock_path: Path):
        import fcntl

        lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        handle = lock_path.open("a+b")
        os.chmod(lock_path, 0o600)
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise DesktopStorageError("local Matter storage is already in use") from exc
        return handle

    def _open(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, isolation_level=None, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        if self.database_path.exists():
            os.chmod(self.database_path, 0o600)
        return connection

    def _migrate(self) -> None:
        with self._transaction():
            self._connection.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value BLOB NOT NULL)")
            current = self._connection.execute("SELECT value FROM metadata WHERE key = 'schema_version'").fetchone()
            if current is None:
                self._connection.execute("INSERT INTO metadata(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
                self._connection.execute("CREATE TABLE matters (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, nonce BLOB NOT NULL, payload BLOB NOT NULL)")
                self._connection.execute("CREATE TABLE events (id TEXT PRIMARY KEY, matter_id TEXT NOT NULL REFERENCES matters(id), event_date TEXT NOT NULL, created_at TEXT NOT NULL, fingerprint TEXT, nonce BLOB NOT NULL, payload BLOB NOT NULL, UNIQUE(matter_id, fingerprint))")
                nonce, encrypted = self._encrypt(_CHECK_VALUE, b"metadata:check")
                self._connection.execute("INSERT INTO metadata(key, value) VALUES ('key_check_nonce', ?)", (nonce,))
                self._connection.execute("INSERT INTO metadata(key, value) VALUES ('key_check_payload', ?)", (encrypted,))
            elif int(current["value"]) != SCHEMA_VERSION:
                raise DesktopStorageError("local Matter storage migration is unavailable")
            check = self._connection.execute("SELECT value FROM metadata WHERE key = 'key_check_nonce'").fetchone()
            payload = self._connection.execute("SELECT value FROM metadata WHERE key = 'key_check_payload'").fetchone()
            if check is None or payload is None or self._decrypt(check["value"], payload["value"], b"metadata:check") != _CHECK_VALUE:
                raise DesktopStorageError("local Matter storage key cannot open existing data")

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        with self._mutex:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                yield
            except Exception:
                self._connection.execute("ROLLBACK")
                raise
            else:
                self._connection.execute("COMMIT")

    def _encrypt(self, value: bytes, aad: bytes) -> tuple[bytes, bytes]:
        nonce = os.urandom(12)
        return nonce, self._cipher.encrypt(nonce, value, aad)

    def _decrypt(self, nonce: bytes, payload: bytes, aad: bytes) -> bytes:
        try:
            return self._cipher.decrypt(nonce, payload, aad)
        except InvalidTag as exc:
            raise DesktopStorageError("local Matter storage integrity verification failed") from exc

    @staticmethod
    def _json(model) -> bytes:
        return model.model_dump_json().encode("utf-8")

    @staticmethod
    def _matter(row: sqlite3.Row, payload: bytes) -> Matter:
        return Matter.model_validate_json(payload)

    @staticmethod
    def _event(row: sqlite3.Row, payload: bytes) -> MatterEvent:
        return MatterEvent.model_validate_json(payload)

    def create(self, matter: Matter) -> Matter:
        nonce, payload = self._encrypt(self._json(matter), f"matter:{matter.id}".encode())
        with self._transaction():
            self._connection.execute("INSERT INTO matters(id, created_at, updated_at, nonce, payload) VALUES (?, ?, ?, ?, ?)", (matter.id, matter.created_at.isoformat(), matter.updated_at.isoformat(), nonce, payload))
        return matter

    def get(self, matter_id: str) -> Matter | None:
        with self._mutex:
            row = self._connection.execute("SELECT * FROM matters WHERE id = ?", (matter_id,)).fetchone()
            if row is None:
                return None
            return self._matter(row, self._decrypt(row["nonce"], row["payload"], f"matter:{matter_id}".encode()))

    def list_matters(self) -> list[Matter]:
        with self._mutex:
            rows = self._connection.execute("SELECT * FROM matters ORDER BY updated_at DESC").fetchall()
            return [self._matter(row, self._decrypt(row["nonce"], row["payload"], f"matter:{row['id']}".encode())) for row in rows]

    def _save_matter(self, matter: Matter) -> Matter:
        nonce, payload = self._encrypt(self._json(matter), f"matter:{matter.id}".encode())
        self._connection.execute("UPDATE matters SET updated_at = ?, nonce = ?, payload = ? WHERE id = ?", (matter.updated_at.isoformat(), nonce, payload, matter.id))
        return matter

    def add_deadlines(self, matter_id: str, deadlines: list[Deadline]) -> Matter | None:
        with self._transaction():
            matter = self.get(matter_id)
            if matter is None:
                return None
            existing = {(item.title, item.due_date, item.source_text) for item in matter.deadlines}
            for deadline in deadlines:
                if (deadline.title, deadline.due_date, deadline.source_text) not in existing:
                    matter.deadlines.append(deadline)
            if deadlines:
                matter.updated_at = utcnow()
                self._save_matter(matter)
            return matter

    def add_event(self, matter_id: str, title: str, event_date: datetime, description: str | None = None, source_document: str | None = None, document_fingerprint: str | None = None) -> MatterEvent | None:
        with self._transaction():
            if self.get(matter_id) is None:
                return None
            if document_fingerprint:
                existing = self.event_by_fingerprint(matter_id, document_fingerprint)
                if existing is not None:
                    return existing
            event = MatterEvent(id=uuid4().hex, matter_id=matter_id, title=title, event_date=event_date, description=description, source_document=source_document, document_fingerprint=document_fingerprint, created_at=utcnow())
            nonce, payload = self._encrypt(self._json(event), f"event:{event.id}".encode())
            self._connection.execute("INSERT INTO events(id, matter_id, event_date, created_at, fingerprint, nonce, payload) VALUES (?, ?, ?, ?, ?, ?, ?)", (event.id, matter_id, event.event_date.isoformat(), event.created_at.isoformat(), document_fingerprint, nonce, payload))
            matter = self.get(matter_id)
            assert matter is not None
            matter.updated_at = utcnow()
            self._save_matter(matter)
            return event

    def record_document_event(self, matter_id: str, title: str, event_date: datetime, description: str | None = None, source_document: str | None = None, document_fingerprint: str | None = None, deadlines: list[Deadline] | None = None) -> MatterEvent | None:
        with self._transaction():
            if document_fingerprint:
                existing = self.event_by_fingerprint(matter_id, document_fingerprint)
                if existing is not None:
                    return existing
            matter = self.get(matter_id)
            if matter is None:
                return None
            existing_deadlines = {(item.title, item.due_date, item.source_text) for item in matter.deadlines}
            for deadline in deadlines or []:
                if (deadline.title, deadline.due_date, deadline.source_text) not in existing_deadlines:
                    matter.deadlines.append(deadline)
            event = MatterEvent(id=uuid4().hex, matter_id=matter_id, title=title, event_date=event_date, description=description, source_document=source_document, document_fingerprint=document_fingerprint, created_at=utcnow())
            nonce, payload = self._encrypt(self._json(event), f"event:{event.id}".encode())
            self._connection.execute("INSERT INTO events(id, matter_id, event_date, created_at, fingerprint, nonce, payload) VALUES (?, ?, ?, ?, ?, ?, ?)", (event.id, matter_id, event.event_date.isoformat(), event.created_at.isoformat(), document_fingerprint, nonce, payload))
            matter.updated_at = utcnow()
            self._save_matter(matter)
            return event

    def event_by_fingerprint(self, matter_id: str, document_fingerprint: str) -> MatterEvent | None:
        with self._mutex:
            row = self._connection.execute("SELECT * FROM events WHERE matter_id = ? AND fingerprint = ?", (matter_id, document_fingerprint)).fetchone()
            if row is None:
                return None
            return self._event(row, self._decrypt(row["nonce"], row["payload"], f"event:{row['id']}".encode()))

    def events(self, matter_id: str) -> list[MatterEvent]:
        with self._mutex:
            rows = self._connection.execute("SELECT * FROM events WHERE matter_id = ? ORDER BY event_date", (matter_id,)).fetchall()
            return [self._event(row, self._decrypt(row["nonce"], row["payload"], f"event:{row['id']}".encode())) for row in rows]

    def close(self) -> None:
        with self._mutex:
            self._connection.close()
            self._lock_handle.close()
