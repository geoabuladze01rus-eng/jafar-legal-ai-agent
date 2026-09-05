from __future__ import annotations

import base64
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from jafar.domains import MatterType
from jafar.encrypted_sqlite_matter_repository import (
    DesktopStorageError,
    EncryptedSQLiteMatterRepository,
    storage_key_from_environment,
)
from jafar.legal_models import Matter


def make_matter(marker: str = "SYNTHETIC-LEGAL-MARKER-DO-NOT-LEAK") -> Matter:
    now = datetime.now(timezone.utc)
    return Matter(
        id="matter-1",
        title=marker,
        matter_type=MatterType.GENERAL,
        client_name="Synthetic Client",
        created_at=now,
        updated_at=now,
    )


def storage_key(monkeypatch, value: bytes = b"k" * 32) -> bytes:
    monkeypatch.setenv("JAFAR_DESKTOP_STORAGE_KEY", base64.urlsafe_b64encode(value).decode().rstrip("="))
    return storage_key_from_environment()


def repository(tmp_path: Path, key: bytes) -> EncryptedSQLiteMatterRepository:
    return EncryptedSQLiteMatterRepository(tmp_path / "matters.sqlite3", key, tmp_path / "matters.lock")


def test_encrypted_matter_persists_across_restart_without_plaintext_marker(tmp_path, monkeypatch):
    key = storage_key(monkeypatch)
    first = repository(tmp_path, key)
    first.create(make_matter())
    first.close()

    raw = (tmp_path / "matters.sqlite3").read_bytes()
    assert b"SYNTHETIC-LEGAL-MARKER-DO-NOT-LEAK" not in raw

    second = repository(tmp_path, key)
    assert second.get("matter-1").title == "SYNTHETIC-LEGAL-MARKER-DO-NOT-LEAK"
    second.close()


def test_wrong_key_fails_closed_without_resetting_existing_database(tmp_path, monkeypatch):
    first = repository(tmp_path, storage_key(monkeypatch))
    first.create(make_matter())
    first.close()

    with pytest.raises(DesktopStorageError):
        repository(tmp_path, storage_key(monkeypatch, b"w" * 32))
    assert (tmp_path / "matters.sqlite3").exists()


def test_tampered_payload_fails_authenticated_integrity_check(tmp_path, monkeypatch):
    store = repository(tmp_path, storage_key(monkeypatch))
    store.create(make_matter())
    connection = sqlite3.connect(tmp_path / "matters.sqlite3")
    payload = connection.execute("SELECT payload FROM matters WHERE id = 'matter-1'").fetchone()[0]
    connection.execute("UPDATE matters SET payload = ? WHERE id = 'matter-1'", (payload[:-1] + bytes([payload[-1] ^ 1]),))
    connection.commit()
    connection.close()
    with pytest.raises(DesktopStorageError):
        store.get("matter-1")
    store.close()


def test_schema_migration_refuses_unknown_version_without_deleting_matters(tmp_path, monkeypatch):
    store = repository(tmp_path, storage_key(monkeypatch))
    store.create(make_matter())
    store.close()
    connection = sqlite3.connect(tmp_path / "matters.sqlite3")
    connection.execute("UPDATE metadata SET value = '999' WHERE key = 'schema_version'")
    connection.commit()
    connection.close()
    with pytest.raises(DesktopStorageError):
        repository(tmp_path, storage_key(monkeypatch))
    assert (tmp_path / "matters.sqlite3").exists()


def test_second_writer_is_rejected_and_atomic_duplicate_failure_preserves_existing_data(tmp_path, monkeypatch):
    key = storage_key(monkeypatch)
    first = repository(tmp_path, key)
    first.create(make_matter())
    with pytest.raises(DesktopStorageError):
        repository(tmp_path, key)
    with pytest.raises(sqlite3.IntegrityError):
        first.create(make_matter())
    assert first.get("matter-1") is not None
    first.close()
