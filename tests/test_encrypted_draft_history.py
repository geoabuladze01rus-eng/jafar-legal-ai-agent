"""Private legal draft retention, history, conflict and API tests (synthetic data only)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jafar.api_auth import api_auth_middleware
from jafar.domains import MatterType
from jafar.draft_history_api import build_draft_history_router
from jafar.encrypted_draft_history import (
    DraftHistoryConflict,
    DraftHistoryNotFound,
    EncryptedDraftHistory,
    derive_draft_history_key,
)
from jafar.encrypted_sqlite_matter_repository import DesktopStorageError
from jafar.legal_draft_service import LegalDraftRequest
from jafar.legal_models import Matter
from jafar.matters import MatterStore


def request(position: str = "Учебная позиция") -> LegalDraftRequest:
    return LegalDraftRequest(
        kind="complaint",
        recipient="Синтетический суд",
        author="Тестовый заявитель",
        position=position,
        legal_basis="Проверяемое пользователем правовое основание",
        requested_action="Рассмотреть доводы",
        source_document_ids=["synthetic-a"],
    )


def build_store(tmp_path) -> EncryptedDraftHistory:
    return EncryptedDraftHistory(
        tmp_path / "drafts.sqlite3",
        derive_draft_history_key(bytes.fromhex("37" * 32)),
    )


def matter_store() -> MatterStore:
    store = MatterStore()
    now = datetime.now(timezone.utc)
    for key in ("case-a", "case-b"):
        store.create(
            Matter(
                id=key, title="Учебное дело " + key,
                matter_type=MatterType.CRIMINAL,
                created_at=now, updated_at=now,
            )
        )
    return store


def test_private_encrypted_revisions_survive_restart_without_plaintext(tmp_path):
    store = build_store(tmp_path)
    created = store.create("case-a", request("Секретная тестовая фраза"))
    saved = store.save(
        "case-a", created.draft_id,
        expected_revision=1, draft=request("Уточнённая секретная фраза"),
    )
    assert saved.revision == 2
    assert store.get("case-a", created.draft_id, 1).draft.position == "Секретная тестовая фраза"
    assert store.get("case-a", created.draft_id).draft.position == "Уточнённая секретная фраза"
    assert [v.revision for v in store.versions("case-a", created.draft_id)] == [2, 1]

    store.close()
    database = (tmp_path / "drafts.sqlite3").read_bytes()
    assert "Секретная тестовая фраза".encode("utf-8") not in database
    assert "Уточнённая секретная фраза".encode("utf-8") not in database
    restarted = build_store(tmp_path)
    assert restarted.get("case-a", created.draft_id).draft.position == "Уточнённая секретная фраза"
    restarted.close()


def test_reject_other_matter_draft_and_never_include_foreign_metadata(tmp_path):
    store = build_store(tmp_path)
    created = store.create("case-a", request("Секрет дела A"))
    assert store.list("case-b") == []
    with pytest.raises(DraftHistoryNotFound):
        store.get("case-b", created.draft_id)
    with pytest.raises(DraftHistoryNotFound):
        store.save("case-b", created.draft_id, expected_revision=1, draft=request("Атака"))
    with pytest.raises(DraftHistoryNotFound):
        store.versions("case-b", created.draft_id)
    store.close()


def test_revision_conflict_never_overwrites_newer_user_work(tmp_path):
    store = build_store(tmp_path)
    created = store.create("case-a", request("Первая версия"))
    second = store.save(
        "case-a", created.draft_id, expected_revision=1, draft=request("Вторая версия"),
    )
    with pytest.raises(DraftHistoryConflict):
        store.save(
            "case-a", created.draft_id, expected_revision=1, draft=request("Устаревшая запись"),
        )
    assert store.get("case-a", created.draft_id).draft.position == "Вторая версия"
    assert second.revision == 2
    store.close()


def test_encrypted_archive_fails_closed_on_wrong_key_and_tampering(tmp_path):
    store = build_store(tmp_path)
    created = store.create("case-a", request("Защищённые данные"))
    store.close()
    with pytest.raises(DesktopStorageError):
        EncryptedDraftHistory(
            tmp_path / "drafts.sqlite3",
            derive_draft_history_key(bytes.fromhex("42" * 32)),
        )

    connection = sqlite3.connect(tmp_path / "drafts.sqlite3")
    connection.execute(
        "UPDATE draft_revisions SET payload=? WHERE draft_id=? AND revision=1",
        (b"corrupted", created.draft_id),
    )
    connection.commit()
    connection.close()
    correct = build_store(tmp_path)
    with pytest.raises(DesktopStorageError):
        correct.get("case-a", created.draft_id)
    correct.close()


def test_missing_identity_in_existing_database_does_not_replace_encrypted_history(tmp_path):
    db = tmp_path / "drafts.sqlite3"
    db.write_bytes(b"")
    with pytest.raises(DesktopStorageError):
        build_store(tmp_path)


def test_authentication_version_restore_and_local_only_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("JAFAR_RUNTIME_MODE", "desktop")
    monkeypatch.setenv("JAFAR_DESKTOP_IPC_TOKEN", "fake-private-test-token-more-than-32-chars")
    db = build_store(tmp_path)
    app = FastAPI()
    app.middleware("http")(api_auth_middleware)
    app.include_router(build_draft_history_router(matter_store(), db))
    client = TestClient(app)
    url = "/v1/matters/case-a/drafts"

    assert client.get(url).status_code == 401
    headers = {"Authorization": "Bearer fake-private-test-token-more-than-32-chars"}
    response = client.post(url, json={"draft": request().model_dump(mode="json")}, headers=headers)
    assert response.status_code == 201, response.text
    doc = response.json()
    draft_id = doc["draft_id"]
    assert doc["revision"] == 1

    foreign = client.get(
        "/v1/matters/case-b/drafts/" + draft_id, headers=headers,
    )
    assert foreign.status_code == 404
    assert "Учебная позиция" not in foreign.text

    v2 = client.put(
        url + "/" + draft_id,
        json={
            "expected_revision": 1,
            "draft": request("Обновлённый текст").model_dump(mode="json"),
        },
        headers=headers,
    )
    assert v2.status_code == 200, v2.text
    assert v2.json()["revision"] == 2
    stale = client.put(
        url + "/" + draft_id,
        json={"expected_revision": 1, "draft": request().model_dump(mode="json")},
        headers=headers,
    )
    assert stale.status_code == 409
    history = client.get(url + "/" + draft_id + "/revisions", headers=headers)
    assert history.status_code == 200
    assert [item["revision"] for item in history.json()] == [2, 1]

    forbidden = client.post(
        url + "/" + draft_id + "/restore",
        json={"expected_revision": 2, "source_revision": 1, "approved": False},
        headers=headers,
    )
    assert forbidden.status_code == 403
    restored = client.post(
        url + "/" + draft_id + "/restore",
        json={"expected_revision": 2, "source_revision": 1, "approved": True},
        headers=headers,
    )
    assert restored.status_code == 200
    assert restored.json()["revision"] == 3
    assert restored.json()["draft"]["position"] == "Учебная позиция"
    assert client.get(url, headers=headers).json()[0]["revision"] == 3
    db.close()

    remote = FastAPI()
    remote.include_router(build_draft_history_router(matter_store(), None))
    assert TestClient(remote).get(url).status_code == 404


def test_swift_history_has_protected_api_and_no_plaintext_userdefaults():
    from pathlib import Path

    root = Path(__file__).parents[1]
    client = (root / "apple/JafarApp/JusticiaAPIClient.swift").read_text(encoding="utf-8")
    panel = (root / "apple/JafarApp/JusticiaDraftHistoryPanel.swift").read_text(encoding="utf-8")
    composer = (root / "apple/JafarApp/JusticiaDraftComposerView.swift").read_text(encoding="utf-8")
    assert 'path: "/v1/matters/\\(matterID)/drafts"' in client
    assert "expectedRevision: expectedRevision" in client
    assert "JusticiaDraftHistoryPanel(" in composer
    assert "Текст хранится в зашифрованной базе" in panel
    assert "Обнаружена более новая редакция" in panel
    assert "onLoad(restored.draft)" in panel
    assert "UserDefaults.standard.set" not in panel
    assert "Task.sleep(nanoseconds:" in panel
    assert "self.matterID == matterID" in panel
