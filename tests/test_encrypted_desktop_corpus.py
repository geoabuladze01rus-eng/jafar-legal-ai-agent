from __future__ import annotations

import sqlite3
import stat
from pathlib import Path

import pytest

from jafar.case_acceptance import VerificationStatus
from jafar.encrypted_desktop_corpus import EncryptedDesktopCorpusStore
from jafar.encrypted_sqlite_matter_repository import DesktopStorageError
from jafar.matter_rag import MatterChunk


MARKER = "SYNTHETIC-FULL-CORPUS-MARKER-DO-NOT-LEAK"


def store(root: Path, key: bytes = b"k" * 32) -> EncryptedDesktopCorpusStore:
    return EncryptedDesktopCorpusStore(root / "corpus.sqlite3", root / "documents", key)


def persist(target: EncryptedDesktopCorpusStore, matter_id: str = "matter-a"):
    return target.store_document(
        matter_id=matter_id,
        filename="secret-contract.txt",
        media_type="text/plain",
        original_bytes=(MARKER + " original bytes").encode(),
        extracted_text=MARKER + " extracted text for retrieval.",
        ocr_records=({"text": MARKER, "page": 1, "verification": VerificationStatus.OCR_UNVERIFIED.value},),
        facts=({"field": "amount", "value": MARKER, "verification": VerificationStatus.TEXT_LAYER_VERIFIED.value},),
        provenance=({"document_id": "pending", "page": 1, "verification": VerificationStatus.VISUALLY_VERIFIED.value},),
        chunks=(MatterChunk("", matter_id, "", 1, 0, MARKER + " chunk text"),),
    )


def test_full_corpus_survives_restart_without_plaintext(tmp_path: Path):
    first = store(tmp_path)
    document = persist(first)
    assert first.read_original("matter-a", document.document_id).startswith(MARKER.encode())
    assert first.retrieve("matter-a", MARKER).citations == (
        f"document:{document.document_id}:page:1:chunk:0",
    )
    first.close()

    for path in (path for path in tmp_path.rglob("*") if path.is_file()):
        assert MARKER.encode() not in path.read_bytes()
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "documents").stat().st_mode) == 0o700

    second = store(tmp_path)
    restored = second.get_document("matter-a", document.document_id)
    assert restored is not None
    assert restored.extracted_text.startswith(MARKER)
    assert restored.ocr_records[0]["verification"] == VerificationStatus.OCR_UNVERIFIED.value
    assert restored.provenance[0]["verification"] == VerificationStatus.VISUALLY_VERIFIED.value
    assert second.retrieve("matter-a", MARKER).citations == (
        f"document:{document.document_id}:page:1:chunk:0",
    )
    assert second.verify_document("matter-a", document.document_id) == "READY"
    second.close()


def test_wrong_key_and_tampered_blob_fail_closed(tmp_path: Path):
    first = store(tmp_path)
    document = persist(first)
    first.close()
    with pytest.raises(DesktopStorageError):
        store(tmp_path, b"w" * 32)

    second = store(tmp_path)
    blob = tmp_path / "documents" / f"{document.document_id}.jafarblob"
    payload = blob.read_bytes()
    blob.write_bytes(payload[:-1] + bytes([payload[-1] ^ 1]))
    with pytest.raises(DesktopStorageError):
        second.read_original("matter-a", document.document_id)
    second.close()


def test_matter_isolation_and_failed_ingest_do_not_leave_ready_data(tmp_path: Path):
    target = store(tmp_path)
    first = persist(target, "matter-a")
    second = persist(target, "matter-b")
    assert MARKER in target.retrieve("matter-a", MARKER).render()
    assert second.document_id not in target.retrieve("matter-a", MARKER).render()
    assert target.get_document("matter-b", first.document_id) is None
    with pytest.raises(ValueError):
        target.store_document(
            matter_id="matter-a", filename="bad.txt", media_type="text/plain", original_bytes=b"bad",
            extracted_text="bad", chunks=(MatterChunk("", "matter-b", "", 1, 0, "bad"),),
        )
    assert len(target.documents("matter-a")) == 1
    assert not list((tmp_path / "documents").glob("*.tmp"))
    target.close()


def test_unknown_schema_and_unapproved_delete_fail_closed(tmp_path: Path):
    target = store(tmp_path)
    document = persist(target)
    with pytest.raises(PermissionError):
        target.delete_document("matter-a", document.document_id, approved=False)
    assert target.get_document("matter-a", document.document_id) is not None
    assert target.delete_document("matter-a", document.document_id, approved=True)
    assert target.get_document("matter-a", document.document_id) is None
    assert not (tmp_path / "documents" / f"{document.document_id}.jafarblob").exists()
    target.close()
    connection = sqlite3.connect(tmp_path / "corpus.sqlite3")
    connection.execute("UPDATE metadata SET value = '999' WHERE key = 'schema_version'")
    connection.commit()
    connection.close()
    with pytest.raises(DesktopStorageError):
        store(tmp_path)
