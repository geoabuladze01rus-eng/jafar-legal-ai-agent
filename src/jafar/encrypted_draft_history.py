"""Encrypted local draft revision history for the standalone macOS runtime.

This is intentionally independent of Supabase and document ingestion. Draft text,
recipients, source IDs and legal grounds never appear in plaintext SQLite columns.
Saving a revision requires the previously observed revision number.
"""

from __future__ import annotations

import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Iterator
from uuid import uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from pydantic import BaseModel, Field

from .encrypted_sqlite_matter_repository import DesktopStorageError
from .legal_draft_service import LegalDraftRequest


_HISTORY_KEY_INFO = b"jafar-desktop-draft-revisions-v1"
_HISTORY_KEY_SALT = b"jafar-desktop-isolated-drafts"
_CHECK = b"JAFAR-DRAFTS-ENCRYPTION-CHECK-v1"
_MAX_REVISIONS = 200


def derive_draft_history_key(corpus_key: bytes) -> bytes:
    if len(corpus_key) != 32:
        raise DesktopStorageError("Invalid desktop draft history key material")
    return HKDF(
        algorithm=SHA256(),
        length=32,
        salt=_HISTORY_KEY_SALT,
        info=_HISTORY_KEY_INFO,
    ).derive(corpus_key)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DraftHistoryConflict(RuntimeError):
    pass


class DraftHistoryNotFound(RuntimeError):
    pass


class DraftHistoryLimit(RuntimeError):
    pass


class DraftRevision(BaseModel):
    draft_id: str
    matter_id: str
    revision: int
    created_at: str
    saved_at: str
    draft: LegalDraftRequest


class DraftSummary(BaseModel):
    draft_id: str
    matter_id: str
    revision: int
    created_at: str
    updated_at: str
    kind: str
    label: str


class DraftRevisionInfo(BaseModel):
    revision: int
    saved_at: str


class DraftSaveRequest(BaseModel):
    expected_revision: int = Field(ge=1, le=_MAX_REVISIONS)
    draft: LegalDraftRequest


class EncryptedDraftHistory:
    """Append-only encrypted revision snapshots with optimistic concurrency."""

    def __init__(self, path: Path, key: bytes) -> None:
        if len(key) != 32:
            raise DesktopStorageError("Invalid local draft storage key")
        self.path = path
        self._cipher = AESGCM(key)
        self._lock = RLock()
        existed = path.exists()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            path.parent.chmod(0o700)
        except OSError:
            pass
        self._db = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("PRAGMA foreign_keys=ON")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        try:
            self._migrate(existed=existed)
        except Exception:
            self._db.close()
            raise

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise

    def _seal(self, data: bytes, associated_data: bytes) -> tuple[bytes, bytes]:
        nonce = os.urandom(12)
        return nonce, self._cipher.encrypt(nonce, data, associated_data)

    def _open(self, nonce: bytes, ciphertext: bytes, associated_data: bytes) -> bytes:
        try:
            return self._cipher.decrypt(nonce, ciphertext, associated_data)
        except (InvalidTag, ValueError, TypeError) as exc:
            raise DesktopStorageError("Local draft integrity check failed") from exc

    def _migrate(self, *, existed: bool) -> None:
        with self._transaction():
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS draft_metadata "
                "(key TEXT PRIMARY KEY, nonce BLOB NOT NULL, value BLOB NOT NULL)"
            )
            row = self._db.execute(
                "SELECT nonce,value FROM draft_metadata WHERE key='key_check'"
            ).fetchone()
            if row is None:
                if existed:
                    raise DesktopStorageError("Existing draft database has no encryption identity")
                self._db.execute(
                    "CREATE TABLE drafts "
                    "(id TEXT PRIMARY KEY, matter_id TEXT NOT NULL, revision INTEGER NOT NULL,"
                    " created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
                )
                self._db.execute(
                    "CREATE INDEX drafts_matter_idx ON drafts(matter_id, updated_at)"
                )
                self._db.execute(
                    "CREATE TABLE draft_revisions "
                    "(draft_id TEXT NOT NULL REFERENCES drafts(id) ON DELETE CASCADE,"
                    " revision INTEGER NOT NULL, saved_at TEXT NOT NULL,"
                    " nonce BLOB NOT NULL, payload BLOB NOT NULL,"
                    " PRIMARY KEY (draft_id, revision))"
                )
                nonce, ciphertext = self._seal(_CHECK, b"draft-metadata:key-check")
                self._db.execute(
                    "INSERT INTO draft_metadata (key,nonce,value) VALUES ('key_check',?,?)",
                    (nonce, ciphertext),
                )
            else:
                if self._open(row["nonce"], row["value"], b"draft-metadata:key-check") != _CHECK:
                    raise DesktopStorageError("Local draft key mismatch")
                required = {"drafts", "draft_revisions"}
                existing = {
                    record["name"] for record in self._db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                if not required.issubset(existing):
                    raise DesktopStorageError("Incomplete local draft history schema")

    @staticmethod
    def _aad(matter_id: str, draft_id: str, revision: int) -> bytes:
        return f"draft:{matter_id}:{draft_id}:{revision}".encode("utf-8")

    def _new_snapshot(self, matter_id: str, draft_id: str, revision: int, draft: LegalDraftRequest) -> tuple[bytes, bytes]:
        return self._seal(
            draft.model_dump_json().encode("utf-8"),
            self._aad(matter_id, draft_id, revision),
        )

    def _read_snapshot(self, row: sqlite3.Row) -> LegalDraftRequest:
        cleartext = self._open(
            row["nonce"], row["payload"],
            self._aad(row["matter_id"], row["draft_id"], row["revision"]),
        )
        try:
            return LegalDraftRequest.model_validate_json(cleartext)
        except (ValueError, TypeError) as exc:
            raise DesktopStorageError("Local draft payload is invalid") from exc

    def _parent(self, matter_id: str, draft_id: str) -> sqlite3.Row:
        row = self._db.execute(
            "SELECT * FROM drafts WHERE id=? AND matter_id=?",
            (draft_id, matter_id),
        ).fetchone()
        if row is None:
            raise DraftHistoryNotFound("Draft not found in selected Matter")
        return row

    def create(self, matter_id: str, draft: LegalDraftRequest) -> DraftRevision:
        if not matter_id:
            raise ValueError("Matter ID required")
        draft_id = str(uuid4())
        saved_at = _utc_now()
        nonce, encrypted = self._new_snapshot(matter_id, draft_id, 1, draft)
        with self._transaction():
            self._db.execute(
                "INSERT INTO drafts(id,matter_id,revision,created_at,updated_at) VALUES (?,?,?,?,?)",
                (draft_id, matter_id, 1, saved_at, saved_at),
            )
            self._db.execute(
                "INSERT INTO draft_revisions(draft_id,revision,saved_at,nonce,payload) VALUES (?,?,?,?,?)",
                (draft_id, 1, saved_at, nonce, encrypted),
            )
        return self.get(matter_id, draft_id)

    def get(self, matter_id: str, draft_id: str, revision: int | None = None) -> DraftRevision:
        with self._lock:
            parent = self._parent(matter_id, draft_id)
            target = revision if revision is not None else parent["revision"]
            row = self._db.execute(
                "SELECT r.draft_id,r.revision,r.saved_at,r.nonce,r.payload,"
                "d.matter_id,d.created_at FROM draft_revisions r "
                "JOIN drafts d ON d.id=r.draft_id "
                "WHERE d.id=? AND d.matter_id=? AND r.revision=?",
                (draft_id, matter_id, target),
            ).fetchone()
            if row is None:
                raise DraftHistoryNotFound("Draft revision not found")
            draft = self._read_snapshot(row)
            return DraftRevision(
                draft_id=draft_id,
                matter_id=matter_id,
                revision=target,
                created_at=parent["created_at"],
                saved_at=row["saved_at"],
                draft=draft,
            )

    def list(self, matter_id: str) -> list[DraftSummary]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id,revision,created_at,updated_at FROM drafts "
                "WHERE matter_id=? ORDER BY updated_at DESC,id DESC",
                (matter_id,),
            ).fetchall()
            result: list[DraftSummary] = []
            for row in rows:
                item = self.get(matter_id, row["id"])
                label = item.draft.position.strip()[:85] or item.draft.requested_action.strip()[:85] or "Без названия"
                result.append(
                    DraftSummary(
                        draft_id=item.draft_id,
                        matter_id=matter_id,
                        revision=item.revision,
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        kind=item.draft.kind,
                        label=label,
                    )
                )
            return result

    def versions(self, matter_id: str, draft_id: str) -> list[DraftRevisionInfo]:
        with self._lock:
            self._parent(matter_id, draft_id)
            rows = self._db.execute(
                "SELECT revision,saved_at FROM draft_revisions "
                "WHERE draft_id=? ORDER BY revision DESC",
                (draft_id,),
            ).fetchall()
            return [DraftRevisionInfo(revision=row["revision"], saved_at=row["saved_at"]) for row in rows]

    def save(self, matter_id: str, draft_id: str, *, expected_revision: int, draft: LegalDraftRequest) -> DraftRevision:
        with self._transaction():
            parent = self._parent(matter_id, draft_id)
            if parent["revision"] != expected_revision:
                raise DraftHistoryConflict("The draft was changed in another editor")
            if expected_revision >= _MAX_REVISIONS:
                raise DraftHistoryLimit("Local draft revision limit reached; archive the DOCX first")
            # Confirm prior revision is readable before appending to the audit chain.
            self.get(matter_id, draft_id)
            next_revision = expected_revision + 1
            now = _utc_now()
            nonce, encrypted = self._new_snapshot(matter_id, draft_id, next_revision, draft)
            self._db.execute(
                "INSERT INTO draft_revisions(draft_id,revision,saved_at,nonce,payload) "
                "VALUES(?,?,?,?,?)",
                (draft_id, next_revision, now, nonce, encrypted),
            )
            self._db.execute(
                "UPDATE drafts SET revision=?,updated_at=? "
                "WHERE id=? AND matter_id=? AND revision=?",
                (next_revision, now, draft_id, matter_id, expected_revision),
            )
        return self.get(matter_id, draft_id)

    def close(self) -> None:
        with self._lock:
            self._db.close()
