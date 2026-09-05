"""Encrypted, Matter-scoped document corpus for the standalone macOS runtime.

The store deliberately keeps SQLite query keys minimal and encrypts every legal
payload independently.  Original bytes live in authenticated encrypted blobs so a
large document never has to be embedded in a Matter JSON record.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence
from uuid import uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .encrypted_sqlite_matter_repository import DesktopStorageError
from .matter_rag import MatterChunk, MatterRAGContext, MatterRetriever


CORPUS_SCHEMA_VERSION = 1
_KEY_INFO = b"jafar-desktop-corpus-storage-v1"
_CHECK_VALUE = b"jafar-desktop-corpus-check-v1"
_BLOB_MAGIC = b"JAFARBLOB1"


def corpus_key_from_environment() -> bytes:
    """Derive a corpus-specific key from the Keychain-provided master key."""
    encoded = os.getenv("JAFAR_DESKTOP_STORAGE_KEY", "").strip()
    if not encoded:
        raise DesktopStorageError("desktop storage key is unavailable")
    try:
        master_key = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (ValueError, TypeError) as exc:
        raise DesktopStorageError("desktop storage key is invalid") from exc
    if len(master_key) != 32:
        raise DesktopStorageError("desktop storage key is invalid")
    return HKDF(
        algorithm=SHA256(), length=32, salt=b"JAFAR desktop storage", info=_KEY_INFO
    ).derive(master_key)


@dataclass(frozen=True, slots=True)
class CorpusDocument:
    document_id: str
    matter_id: str
    filename: str
    media_type: str
    fingerprint: str
    byte_count: int
    extracted_text: str
    ocr_records: tuple[dict[str, Any], ...]
    facts: tuple[dict[str, Any], ...]
    provenance: tuple[dict[str, Any], ...]
    state: str
    created_at: str


class EncryptedDesktopCorpusStore:
    """Durable encrypted blobs, metadata, text, provenance and RAG chunks.

    Matter and document identifiers are retained as SQLite keys solely to preserve
    authorization boundaries and deterministic retrieval.  Names, fingerprints,
    corpus text, OCR, facts, provenance, embeddings and chunk content are encrypted.
    """

    def __init__(self, database_path: Path, documents_path: Path, key: bytes) -> None:
        self.database_path = database_path
        self.documents_path = documents_path
        self._cipher = AESGCM(key)
        self._connection = self._open()
        self._migrate()
        self._cleanup_orphan_blobs()

    def _open(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.documents_path.mkdir(mode=0o700, parents=True, exist_ok=True)
        for path in (self.database_path.parent, self.documents_path):
            try:
                path.chmod(0o700)
            except OSError:
                pass
        connection = sqlite3.connect(self.database_path, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        if self.database_path.exists():
            os.chmod(self.database_path, 0o600)
        return connection

    def _migrate(self) -> None:
        with self._transaction():
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value BLOB NOT NULL)"
            )
            version = self._connection.execute(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            ).fetchone()
            if version is None:
                self._connection.execute(
                    "INSERT INTO metadata(key, value) VALUES ('schema_version', ?)",
                    (str(CORPUS_SCHEMA_VERSION),),
                )
                self._connection.execute(
                    "CREATE TABLE documents (id TEXT PRIMARY KEY, matter_id TEXT NOT NULL, "
                    "created_at TEXT NOT NULL, state TEXT NOT NULL, nonce BLOB NOT NULL, "
                    "payload BLOB NOT NULL)"
                )
                self._connection.execute(
                    "CREATE INDEX documents_matter_idx ON documents(matter_id, created_at)"
                )
                self._connection.execute(
                    "CREATE TABLE chunks (id TEXT PRIMARY KEY, matter_id TEXT NOT NULL, "
                    "document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE, source_page INTEGER NOT NULL, "
                    "chunk_index INTEGER NOT NULL, nonce BLOB NOT NULL, payload BLOB NOT NULL, "
                    "UNIQUE(document_id, chunk_index))"
                )
                self._connection.execute(
                    "CREATE INDEX chunks_matter_idx ON chunks(matter_id, document_id, chunk_index)"
                )
                nonce, encrypted = self._encrypt(_CHECK_VALUE, b"metadata:check")
                self._connection.execute(
                    "INSERT INTO metadata(key, value) VALUES ('key_check_nonce', ?)", (nonce,)
                )
                self._connection.execute(
                    "INSERT INTO metadata(key, value) VALUES ('key_check_payload', ?)", (encrypted,)
                )
            elif int(version["value"]) != CORPUS_SCHEMA_VERSION:
                raise DesktopStorageError("desktop corpus migration is unavailable")
            nonce = self._connection.execute(
                "SELECT value FROM metadata WHERE key = 'key_check_nonce'"
            ).fetchone()
            payload = self._connection.execute(
                "SELECT value FROM metadata WHERE key = 'key_check_payload'"
            ).fetchone()
            if nonce is None or payload is None or self._decrypt(
                nonce["value"], payload["value"], b"metadata:check"
            ) != _CHECK_VALUE:
                raise DesktopStorageError("desktop corpus key cannot open existing data")

    @contextmanager
    def _transaction(self) -> Iterator[None]:
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

    def _decrypt(self, nonce: bytes, value: bytes, aad: bytes) -> bytes:
        try:
            return self._cipher.decrypt(nonce, value, aad)
        except InvalidTag as exc:
            raise DesktopStorageError("desktop corpus integrity verification failed") from exc

    @staticmethod
    def _encode(value: dict[str, Any]) -> bytes:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def _decode(value: bytes) -> dict[str, Any]:
        try:
            parsed = json.loads(value.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DesktopStorageError("desktop corpus payload is invalid") from exc
        if not isinstance(parsed, dict):
            raise DesktopStorageError("desktop corpus payload is invalid")
        return parsed

    def _document_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        return self._decode(
            self._decrypt(row["nonce"], row["payload"], f"document:{row['id']}".encode())
        )

    def _chunk_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        return self._decode(self._decrypt(row["nonce"], row["payload"], f"chunk:{row['id']}".encode()))

    def _blob_path(self, document_id: str) -> Path:
        return self.documents_path / f"{document_id}.jafarblob"

    def _write_blob(self, document_id: str, fingerprint: str, content: bytes) -> None:
        target = self._blob_path(document_id)
        if target.exists():
            raise DesktopStorageError("desktop corpus blob already exists")
        nonce, encrypted = self._encrypt(content, f"blob:{document_id}:{fingerprint}".encode())
        temporary = self.documents_path / f".{document_id}.{uuid4().hex}.tmp"
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(_BLOB_MAGIC + nonce + encrypted)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            os.chmod(target, 0o600)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def _read_blob(self, document_id: str, fingerprint: str) -> bytes:
        path = self._blob_path(document_id)
        try:
            value = path.read_bytes()
        except OSError as exc:
            raise DesktopStorageError("desktop corpus blob is missing") from exc
        if not value.startswith(_BLOB_MAGIC) or len(value) <= len(_BLOB_MAGIC) + 12:
            raise DesktopStorageError("desktop corpus blob is corrupt")
        nonce = value[len(_BLOB_MAGIC) : len(_BLOB_MAGIC) + 12]
        encrypted = value[len(_BLOB_MAGIC) + 12 :]
        return self._decrypt(nonce, encrypted, f"blob:{document_id}:{fingerprint}".encode())

    def _cleanup_orphan_blobs(self) -> None:
        known = {row["id"] for row in self._connection.execute("SELECT id FROM documents")}
        for candidate in self.documents_path.glob("*.jafarblob"):
            if candidate.stem not in known:
                candidate.unlink(missing_ok=True)
        for candidate in self.documents_path.glob(".*.tmp"):
            candidate.unlink(missing_ok=True)

    def store_document(
        self,
        *,
        matter_id: str,
        filename: str,
        media_type: str,
        original_bytes: bytes,
        extracted_text: str,
        ocr_records: Sequence[dict[str, Any]] = (),
        facts: Sequence[dict[str, Any]] = (),
        provenance: Sequence[dict[str, Any]] = (),
        chunks: Sequence[MatterChunk] = (),
    ) -> CorpusDocument:
        if not matter_id or not filename or not original_bytes or not extracted_text.strip():
            raise ValueError("complete Matter-scoped document content is required")
        document_id = uuid4().hex
        fingerprint = hashlib.sha256(original_bytes).hexdigest()
        created_at = datetime.now(timezone.utc).isoformat()
        payload = {
            "filename": Path(filename).name,
            "media_type": media_type or "application/octet-stream",
            "fingerprint": fingerprint,
            "byte_count": len(original_bytes),
            "extracted_text": extracted_text,
            "ocr_records": list(ocr_records),
            "facts": list(facts),
            "provenance": list(provenance),
        }
        self._write_blob(document_id, fingerprint, original_bytes)
        try:
            nonce, encrypted = self._encrypt(self._encode(payload), f"document:{document_id}".encode())
            with self._transaction():
                self._connection.execute(
                    "INSERT INTO documents(id, matter_id, created_at, state, nonce, payload) VALUES (?, ?, ?, ?, ?, ?)",
                    (document_id, matter_id, created_at, "READY", nonce, encrypted),
                )
                for index, source in enumerate(chunks):
                    if source.matter_id != matter_id:
                        raise ValueError("RAG chunk belongs to another Matter")
                    source = MatterChunk(
                        chunk_id=f"{document_id}:{index}", matter_id=matter_id,
                        document_id=document_id, source_page=source.source_page,
                        chunk_index=index, content=source.content, embedding=source.embedding,
                    )
                    chunk_payload = {
                        "content": source.content,
                        "embedding": list(source.embedding) if source.embedding is not None else None,
                        "section": getattr(source, "section", None),
                        "fingerprint": fingerprint,
                        "index_version": 1,
                    }
                    chunk_id = source.chunk_id
                    chunk_nonce, chunk_encrypted = self._encrypt(
                        self._encode(chunk_payload), f"chunk:{chunk_id}".encode()
                    )
                    self._connection.execute(
                        "INSERT INTO chunks(id, matter_id, document_id, source_page, chunk_index, nonce, payload) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (chunk_id, matter_id, document_id, source.source_page, source.chunk_index, chunk_nonce, chunk_encrypted),
                    )
        except Exception:
            # It is safe to remove only the newly created encrypted blob: no existing
            # valid document is ever overwritten by a failed transaction.
            self._blob_path(document_id).unlink(missing_ok=True)
            raise
        return self.get_document(matter_id, document_id)  # type: ignore[return-value]

    def get_document(self, matter_id: str, document_id: str) -> CorpusDocument | None:
        row = self._connection.execute(
            "SELECT * FROM documents WHERE id = ? AND matter_id = ?", (document_id, matter_id)
        ).fetchone()
        if row is None:
            return None
        payload = self._document_payload(row)
        return CorpusDocument(
            document_id=document_id, matter_id=matter_id, filename=str(payload["filename"]),
            media_type=str(payload["media_type"]), fingerprint=str(payload["fingerprint"]),
            byte_count=int(payload["byte_count"]), extracted_text=str(payload["extracted_text"]),
            ocr_records=tuple(payload.get("ocr_records", [])), facts=tuple(payload.get("facts", [])),
            provenance=tuple(payload.get("provenance", [])), state=str(row["state"]),
            created_at=str(row["created_at"]),
        )

    def documents(self, matter_id: str) -> list[CorpusDocument]:
        rows = self._connection.execute(
            "SELECT id FROM documents WHERE matter_id = ? ORDER BY created_at", (matter_id,)
        ).fetchall()
        return [document for row in rows if (document := self.get_document(matter_id, row["id"]))]

    def read_original(self, matter_id: str, document_id: str) -> bytes:
        document = self.get_document(matter_id, document_id)
        if document is None:
            raise DesktopStorageError("desktop corpus document is unavailable")
        return self._read_blob(document_id, document.fingerprint)

    def chunks(self, matter_id: str) -> list[MatterChunk]:
        rows = self._connection.execute(
            "SELECT * FROM chunks WHERE matter_id = ? ORDER BY document_id, chunk_index", (matter_id,)
        ).fetchall()
        result: list[MatterChunk] = []
        for row in rows:
            if self.get_document(matter_id, row["document_id"]) is None:
                raise DesktopStorageError("desktop corpus chunk has no authorized document")
            payload = self._chunk_payload(row)
            embedding = payload.get("embedding")
            result.append(MatterChunk(
                chunk_id=row["id"], matter_id=matter_id, document_id=row["document_id"],
                source_page=int(row["source_page"]), chunk_index=int(row["chunk_index"]),
                content=str(payload["content"]),
                embedding=tuple(float(value) for value in embedding) if embedding is not None else None,
            ))
        return result

    def retrieve(self, matter_id: str, query: str, *, limit: int = 8) -> MatterRAGContext:
        return MatterRetriever().retrieve(matter_id=matter_id, query=query, chunks=self.chunks(matter_id), limit=limit)

    def verify_document(self, matter_id: str, document_id: str) -> str:
        """Validate canonical blob and encrypted derived records without logging content."""
        document = self.get_document(matter_id, document_id)
        if document is None:
            raise DesktopStorageError("desktop corpus document is unavailable")
        original = self.read_original(matter_id, document_id)
        if hashlib.sha256(original).hexdigest() != document.fingerprint:
            raise DesktopStorageError("desktop corpus fingerprint verification failed")
        for chunk in self.chunks(matter_id):
            if chunk.document_id == document_id and not chunk.content.strip():
                raise DesktopStorageError("desktop corpus chunk is corrupt")
        return "READY"

    def delete_document(self, matter_id: str, document_id: str, *, approved: bool) -> bool:
        if not approved:
            raise PermissionError("document deletion requires explicit approval")
        document = self.get_document(matter_id, document_id)
        if document is None:
            return False
        with self._transaction():
            self._connection.execute("DELETE FROM documents WHERE id = ? AND matter_id = ?", (document_id, matter_id))
        self._blob_path(document_id).unlink(missing_ok=True)
        return True

    def close(self) -> None:
        self._connection.close()
