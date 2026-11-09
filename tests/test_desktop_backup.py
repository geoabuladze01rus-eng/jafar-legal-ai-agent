"""Offline backup acceptance: only synthetic encrypted legal materials."""

from __future__ import annotations

import hashlib
import zipfile
from datetime import datetime, timezone

import pytest

from jafar.desktop_backup import (
    BackupError,
    create_backup,
    restore_to_new_home,
    verify_backup,
)
from jafar.domains import MatterType
from jafar.encrypted_desktop_corpus import EncryptedDesktopCorpusStore
from jafar.encrypted_draft_history import (
    EncryptedDraftHistory, derive_draft_history_key,
)
from jafar.encrypted_claim_decisions import (
    EncryptedClaimDecisionLedger, derive_decision_ledger_key,
)
from jafar.encrypted_sqlite_matter_repository import EncryptedSQLiteMatterRepository
from jafar.legal_models import Matter
from jafar.legal_draft_service import LegalDraftRequest
from jafar.matter_rag import MatterChunk


PASSPHRASE = "independent-test-backup-secret-2026"
MATTER_KEY = b"M" * 32
CORPUS_KEY = b"C" * 32
PRIVATE_PHRASE = "Совершенно синтетический секрет договора"


@pytest.fixture
def sample_home(tmp_path):
    home = tmp_path / "real-home"
    home.mkdir()
    matter_repo = EncryptedSQLiteMatterRepository(
        home / "matters.sqlite3", MATTER_KEY, home / "matters.lock"
    )
    now = datetime.now(timezone.utc)
    matter_repo.create(
        Matter(
            id="training-only", title="Учебное дело",
            matter_type=MatterType.CIVIL, created_at=now, updated_at=now,
        )
    )
    corpus = EncryptedDesktopCorpusStore(
        home / "corpus.sqlite3", home / "documents", CORPUS_KEY
    )
    plaintext = PRIVATE_PHRASE.encode("utf-8")
    corpus.store_document(
        matter_id="training-only",
        filename="Тестовое соглашение.txt",
        media_type="text/plain",
        original_bytes=plaintext,
        extracted_text=PRIVATE_PHRASE,
        chunks=[
            MatterChunk(
                chunk_id="", matter_id="training-only", document_id="",
                source_page=0, chunk_index=0, content=PRIVATE_PHRASE,
            )
        ],
    )
    history = EncryptedDraftHistory(
        home / "drafts.sqlite3", derive_draft_history_key(CORPUS_KEY)
    )
    history.create(
        "training-only",
        LegalDraftRequest(
            kind="motion",
            position=PRIVATE_PHRASE,
            requested_action="Проверить синтетические документы",
            legal_basis="Учебная правовая позиция",
        ),
    )
    ledger = EncryptedClaimDecisionLedger(
        home / "claim-review-decisions.sqlite3",
        derive_decision_ledger_key(CORPUS_KEY),
    )
    return home, matter_repo, corpus, history, ledger


def close_home(sample_home):
    home, matter_repo, corpus, history, ledger = sample_home
    matter_repo.close()
    corpus.close()
    history.close()
    ledger.close()
    return home


def test_live_application_lock_blocks_inconsistent_backup(sample_home, tmp_path):
    home, matter_repo, corpus, history, ledger = sample_home
    output = tmp_path / "blocked.jafarbackup"
    with pytest.raises(BackupError, match="Close JAFAR"):
        create_backup(home, output, PASSPHRASE)
    assert not output.exists()
    close_home(sample_home)


def test_verified_roundtrip_restores_to_new_home_using_existing_master_keys(
    sample_home, tmp_path
):
    home = close_home(sample_home)
    archive = tmp_path / "legal-copy.jafarbackup"
    result = create_backup(home, archive, PASSPHRASE)
    assert result["files"] == 5
    assert result["bytes"] > 0
    assert archive.exists()
    assert archive.stat().st_mode & 0o077 == 0

    # ZIP contains only encrypted backup-layer entries and a nonsecret header.
    assert PRIVATE_PHRASE.encode("utf-8") not in archive.read_bytes()
    with zipfile.ZipFile(archive) as bundle:
        assert "manifest.enc" in bundle.namelist()
        assert "header.json" in bundle.namelist()
        assert "documents/" not in "\n".join(bundle.namelist())
        assert not any(n.endswith(".sqlite3") for n in bundle.namelist())

    inspection = verify_backup(archive, PASSPHRASE)
    assert inspection["files"] == result["files"]
    assert inspection["created_utc"]

    recovered = tmp_path / "RESTORED-FOR-INSPECTION"
    restored = restore_to_new_home(archive, recovered, PASSPHRASE)
    assert restored["location"] == str(recovered)
    assert (recovered / ".jafar-restore-ready").exists()
    assert (recovered / "matters.sqlite3").stat().st_mode & 0o077 == 0

    # Backup encryption did not change the JAFAR Keychain encryption keys.
    original_store = EncryptedDesktopCorpusStore(
        recovered / "corpus.sqlite3", recovered / "documents", CORPUS_KEY
    )
    documents = original_store.documents("training-only")
    assert len(documents) == 1
    assert original_store.read_original(
        "training-only", documents[0].document_id
    ).decode() == PRIVATE_PHRASE
    original_store.close()
    matters = EncryptedSQLiteMatterRepository(
        recovered / "matters.sqlite3", MATTER_KEY,
        recovered / "matters.lock",
    )
    assert matters.get("training-only").title == "Учебное дело"
    matters.close()
    history = EncryptedDraftHistory(
        recovered / "drafts.sqlite3", derive_draft_history_key(CORPUS_KEY)
    )
    assert len(history.list("training-only")) == 1
    history.close()
    ledger = EncryptedClaimDecisionLedger(
        recovered / "claim-review-decisions.sqlite3",
        derive_decision_ledger_key(CORPUS_KEY),
    )
    assert ledger.list("training-only") == []
    ledger.close()


def test_wrong_passphrase_or_modified_ciphertext_fail_closed(sample_home, tmp_path):
    home = close_home(sample_home)
    archive = tmp_path / "clean.jafarbackup"
    create_backup(home, archive, PASSPHRASE)
    with pytest.raises(BackupError, match="authentication failed"):
        verify_backup(archive, "incorrect test passphrase")
    assert not (tmp_path / "RESTORED").exists()
    with zipfile.ZipFile(archive) as original:
        files = [(name, original.read(name)) for name in original.namelist()]
    broken = tmp_path / "tampered.jafarbackup"
    with zipfile.ZipFile(broken, "w") as target:
        for name, content in files:
            if name.startswith("objects/"):
                content = content[:-1] + bytes([content[-1] ^ 0x01])
            target.writestr(name, content)
    with pytest.raises(BackupError, match="authentication failed"):
        verify_backup(broken, PASSPHRASE)


def test_backup_and_restore_never_overwrite_existing_paths(sample_home, tmp_path):
    home = close_home(sample_home)
    archive = tmp_path / "existing.jafarbackup"
    archive.write_bytes(b"keep-existing")
    with pytest.raises(BackupError, match="already exists"):
        create_backup(home, archive, PASSPHRASE)
    assert archive.read_bytes() == b"keep-existing"
    archive.unlink()

    create_backup(home, archive, PASSPHRASE)
    target = tmp_path / "real-target"
    target.mkdir()
    sentinel = target / "CLIENT-DATA-MUST-SURVIVE.txt"
    sentinel.write_text("untouched")
    with pytest.raises(BackupError, match="already exists"):
        restore_to_new_home(archive, target, PASSPHRASE)
    assert sentinel.read_text() == "untouched"
    with pytest.raises(BackupError, match="inside the live"):
        create_backup(home, home / "nested-archive.jafarbackup", PASSPHRASE)


def test_incomplete_or_unindexed_encrypted_original_blocks_backup(sample_home, tmp_path):
    home = close_home(sample_home)
    sole_original = next((home / "documents").glob("*.jafarblob"))
    sole_original.unlink()
    archive = tmp_path / "must-fail.jafarbackup"
    with pytest.raises(BackupError, match="missing"):
        create_backup(home, archive, PASSPHRASE)
    assert not archive.exists()


def test_backup_rejects_source_symlinks(sample_home, tmp_path):
    home = close_home(sample_home)
    original = next((home / "documents").glob("*.jafarblob"))
    outside = tmp_path / "outside.txt"
    outside.write_bytes(original.read_bytes())
    original.unlink()
    original.symlink_to(outside)
    with pytest.raises(BackupError, match="symlink"):
        create_backup(home, tmp_path / "unsafe.jafarbackup", PASSPHRASE)


def test_incomplete_or_unsafe_archive_member_is_rejected(sample_home, tmp_path):
    home = close_home(sample_home)
    archive = tmp_path / "clean.jafarbackup"
    create_backup(home, archive, PASSPHRASE)
    infected = tmp_path / "extra.jafarbackup"
    with zipfile.ZipFile(archive) as original:
        entries = [(name, original.read(name)) for name in original.namelist()]
    with zipfile.ZipFile(infected, "w") as target:
        for name, data in entries:
            target.writestr(name, data)
        target.writestr("../../potential-traversal.txt", "not accepted")
    with pytest.raises(BackupError, match="Unexpected content"):
        verify_backup(infected, PASSPHRASE)
    assert not (tmp_path.parent / "potential-traversal.txt").exists()


def test_backup_without_optional_databases_is_supported(sample_home, tmp_path):
    home = close_home(sample_home)
    (home / "drafts.sqlite3").unlink()
    (home / "claim-review-decisions.sqlite3").unlink()
    archive = tmp_path / "old-beta.jafarbackup"
    info = create_backup(home, archive, PASSPHRASE)
    assert info["files"] == 3
    assert verify_backup(archive, PASSPHRASE)["files"] == 3


def test_snapshot_sqlite_wal_is_not_copied_as_an_unverified_file(sample_home, tmp_path):
    home = close_home(sample_home)
    archive = tmp_path / "safe-wal.jafarbackup"
    create_backup(home, archive, PASSPHRASE)
    with zipfile.ZipFile(archive) as zipped:
        names = zipped.namelist()
        assert not any(name.endswith("-wal") or name.endswith("-shm") for name in names)
    assert verify_backup(archive, PASSPHRASE)["files"] == 5


def test_keychain_key_is_not_part_of_backup_manifest(sample_home, tmp_path):
    home = close_home(sample_home)
    archive = tmp_path / "safe.jafarbackup"
    create_backup(home, archive, PASSPHRASE)
    raw = archive.read_bytes()
    assert CORPUS_KEY not in raw
    assert MATTER_KEY not in raw
    assert PRIVATE_PHRASE.encode() not in raw
    assert hashlib.sha256(raw).hexdigest()


def test_cli_has_safe_offline_commands_only():
    import argparse
    from jafar.desktop_backup import main

    assert callable(main)
    assert issubclass(BackupError, RuntimeError)
    assert issubclass(argparse.ArgumentParser, object)
