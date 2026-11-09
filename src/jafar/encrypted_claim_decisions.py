"""Append-only encrypted reviewer decision ledger for local legal claim reports.

A user's decision records which proposed comparison they intend to pursue,
dismiss or supplement. It DOES NOT establish that any allegation is true.
Only matter_id, opaque record id and timestamp are plaintext SQLite metadata.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from threading import RLock
from typing import Iterator, Literal
from uuid import uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt
from pydantic import BaseModel, Field, field_validator

from .claim_review import CandidateDifference, GroundedClaim
from .encrypted_sqlite_matter_repository import DesktopStorageError
from .legal_draft_service import _disable_hyphenation, _nobreak_short_words


MAX_EVENTS_PER_MATTER = 300
_KEY_INFO = b"jafar-local-claim-review-decisions-v1"
_SALT = b"jafar-isolated-review-decisions"
_KEY_CHECK = b"JAFAR-REVIEW-DECISION-KEY-CHECK-v1"
Decision = Literal["keep_for_work", "dismissed", "needs_sources"]


def derive_decision_ledger_key(corpus_key: bytes) -> bytes:
    if len(corpus_key) != 32:
        raise DesktopStorageError("Invalid reviewer ledger key material")
    return HKDF(
        algorithm=SHA256(), length=32, salt=_SALT, info=_KEY_INFO
    ).derive(corpus_key)


class ReviewDecisionInput(BaseModel):
    candidate_id: str = Field(min_length=20, max_length=20)
    decision: Decision
    note: str = Field(min_length=5, max_length=2_000)

    @field_validator("candidate_id")
    @classmethod
    def valid_candidate_id(cls, value: str) -> str:
        if any(letter not in "0123456789abcdef" for letter in value):
            raise ValueError("Candidate identifier must be hexadecimal")
        return value

    @field_validator("note")
    @classmethod
    def nonempty_note(cls, value: str) -> str:
        note = value.strip()
        if len(note) < 5:
            raise ValueError("A reason must be recorded")
        return note


class ReviewDecisionRecord(BaseModel):
    record_id: str
    matter_id: str
    candidate_id: str
    decision: Decision
    note: str
    created_at: str
    left: GroundedClaim
    right: GroundedClaim


class ReviewLedgerTooLarge(RuntimeError):
    pass


class EncryptedClaimDecisionLedger:
    """Confidential, append-only local audit events bound to a Matter."""

    def __init__(self, path: Path, key: bytes) -> None:
        if len(key) != 32:
            raise DesktopStorageError("Invalid reviewer ledger key")
        self._lock = RLock()
        self._cipher = AESGCM(key)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            path.parent.chmod(0o700)
        except OSError:
            pass
        existed = path.exists()
        self._db = sqlite3.connect(
            path, isolation_level=None, check_same_thread=False
        )
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        try:
            self._initialize(existed=existed)
        except BaseException:
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

    def _encrypt(self, payload: bytes, aad: bytes) -> tuple[bytes, bytes]:
        nonce = os.urandom(12)
        return nonce, self._cipher.encrypt(nonce, payload, aad)

    def _decrypt(self, nonce: bytes, payload: bytes, aad: bytes) -> bytes:
        try:
            return self._cipher.decrypt(nonce, payload, aad)
        except (InvalidTag, TypeError, ValueError) as exc:
            raise DesktopStorageError("Review decision integrity check failed") from exc

    def _initialize(self, *, existed: bool) -> None:
        with self._transaction():
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS review_metadata"
                " (key TEXT PRIMARY KEY, nonce BLOB NOT NULL, payload BLOB NOT NULL)"
            )
            row = self._db.execute(
                "SELECT nonce,payload FROM review_metadata WHERE key='key_check'"
            ).fetchone()
            if row is None:
                if existed:
                    raise DesktopStorageError("Existing reviewer ledger lacks key identity")
                self._db.execute(
                    "CREATE TABLE review_events ("
                    "id TEXT PRIMARY KEY, matter_id TEXT NOT NULL,"
                    "created_at TEXT NOT NULL, nonce BLOB NOT NULL,"
                    "payload BLOB NOT NULL)"
                )
                self._db.execute(
                    "CREATE INDEX reviewer_matter_events ON"
                    " review_events(matter_id,created_at)"
                )
                nonce, payload = self._encrypt(
                    _KEY_CHECK, b"review-key-check-v1"
                )
                self._db.execute(
                    "INSERT INTO review_metadata(key,nonce,payload)"
                    " VALUES ('key_check',?,?)", (nonce, payload)
                )
            else:
                if self._decrypt(
                    row["nonce"], row["payload"], b"review-key-check-v1"
                ) != _KEY_CHECK:
                    raise DesktopStorageError("Reviewer ledger key mismatch")
                tables = {
                    record["name"] for record in self._db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                if "review_events" not in tables:
                    raise DesktopStorageError("Incomplete reviewer ledger schema")

    @staticmethod
    def _aad(matter_id: str, record_id: str) -> bytes:
        return f"review-event:{matter_id}:{record_id}".encode("utf-8")

    def append(
        self,
        matter_id: str,
        pair: CandidateDifference,
        decision: ReviewDecisionInput,
    ) -> ReviewDecisionRecord:
        if not matter_id or pair.id != decision.candidate_id:
            raise ValueError("Reviewer event does not match selected candidate")
        record_id = str(uuid4())
        event = ReviewDecisionRecord(
            record_id=record_id,
            matter_id=matter_id,
            candidate_id=pair.id,
            decision=decision.decision,
            note=decision.note,
            created_at=datetime.now(timezone.utc).isoformat(),
            left=pair.left,
            right=pair.right,
        )
        nonce, payload = self._encrypt(
            event.model_dump_json().encode("utf-8"),
            self._aad(matter_id, record_id),
        )
        with self._transaction():
            count = self._db.execute(
                "SELECT count(*) FROM review_events WHERE matter_id=?",
                (matter_id,),
            ).fetchone()[0]
            if count >= MAX_EVENTS_PER_MATTER:
                raise ReviewLedgerTooLarge("Reviewer ledger reached its per-Matter limit")
            self._db.execute(
                "INSERT INTO review_events(id,matter_id,created_at,nonce,payload)"
                " VALUES (?,?,?,?,?)",
                (record_id, matter_id, event.created_at, nonce, payload),
            )
        return event

    def list(self, matter_id: str) -> list[ReviewDecisionRecord]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM review_events WHERE matter_id=? "
                "ORDER BY created_at DESC,id DESC", (matter_id,)
            ).fetchall()
            records: list[ReviewDecisionRecord] = []
            for row in rows:
                raw = self._decrypt(
                    row["nonce"], row["payload"],
                    self._aad(matter_id, row["id"]),
                )
                try:
                    event = ReviewDecisionRecord.model_validate_json(raw)
                except (TypeError, ValueError) as exc:
                    raise DesktopStorageError("Corrupted reviewer decision payload") from exc
                if (
                    event.matter_id != matter_id
                    or event.record_id != row["id"]
                    or event.created_at != row["created_at"]
                ):
                    raise DesktopStorageError("Reviewer decision metadata was altered")
                records.append(event)
            return records

    def close(self) -> None:
        with self._lock:
            self._db.close()


def render_review_decisions_docx(
    matter_title: str, records: list[ReviewDecisionRecord]
) -> bytes:
    """Internal register; decisions are user's intent, never verified facts."""
    document = Document()
    section = document.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin, section.bottom_margin = Cm(2), Cm(2)
    section.left_margin, section.right_margin = Cm(3), Cm(1.5)
    normal = document.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)

    def add(text: str) -> None:
        p = document.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_after = Pt(6)
        p.add_run(_nobreak_short_words(text))
        _disable_hyphenation(p)

    add("ВНУТРЕННИЙ РЕЕСТР ПРОВЕРКИ ПРЕДПОЛАГАЕМЫХ РАСХОЖДЕНИЙ")
    add("Дело: " + matter_title)
    labels = {
        "keep_for_work": "Оставить для дальнейшего анализа",
        "dismissed": "Отклонить предположение",
        "needs_sources": "Запросить дополнительные материалы",
    }
    for event in records:
        add("Запись: " + event.created_at)
        add("Решение пользователя: " + labels[event.decision])
        add("Основание решения (со слов пользователя): " + event.note)
        for claim in (event.left, event.right):
            add(
                f"Источник: {claim.filename}; {claim.citation}. "
                f"Дословный фрагмент: «{claim.quote}»"
            )
    add(
        "Решения пользователя отражают рабочую оценку необходимости дальнейшей "
        "проверки. Реестр не удостоверяет подлинность документов, достоверность "
        "показаний, факт противоречия или процессуальные последствия."
    )
    foot = section.footer.paragraphs[0]
    foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    foot.add_run("ВНУТРЕННИЙ РЕЕСТР. НЕ ПРОЦЕССУАЛЬНЫЙ ДОКУМЕНТ.")
    file = BytesIO()
    document.save(file)
    return file.getvalue()
