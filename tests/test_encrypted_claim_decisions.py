"""Encrypted Matter-specific reviewer decisions; all test data are synthetic."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace

import pytest
from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jafar.api_auth import api_auth_middleware
from jafar.claim_decision_api import build_claim_decision_router
from jafar.claim_review import ClaimReviewRequest, ClaimReviewService
from jafar.domains import MatterType
from jafar.encrypted_claim_decisions import (
    EncryptedClaimDecisionLedger,
    ReviewDecisionInput,
    derive_decision_ledger_key,
    render_review_decisions_docx,
)
from jafar.encrypted_sqlite_matter_repository import DesktopStorageError
from jafar.legal_models import Matter
from jafar.matter_rag import MatterChunk
from jafar.matters import MatterStore
from jafar.model_router import ModelResponse


QUOTE_A = "По договору №44 Иванов передал автомобиль 12.05.2026."
QUOTE_B = "По договору №44 Иванов не передал автомобиль 12.05.2026."


def _claim(quote, citation, polarity):
    return {
        "citation": citation, "quote": quote, "subject": "Иванов",
        "event_anchor": "договору №44",
        "action_key": "передача автомобиля", "polarity": polarity,
    }


class FakeCorpus:
    def __init__(self):
        self.documents = {
            ("matter-a", "a"): SimpleNamespace(
                state="READY", filename="Синтетический А.pdf",
                provenance=({"source_page": 1, "page_kind": "pdf_physical"},),
            ),
            ("matter-a", "b"): SimpleNamespace(
                state="READY", filename="Синтетический Б.txt", provenance=(),
            ),
        }
        self.corrupt = False
        self.checked = []

    def get_document(self, matter_id, document_id):
        return self.documents.get((matter_id, document_id))

    def verify_document(self, matter_id, document_id):
        self.checked.append((matter_id, document_id))
        if self.corrupt:
            raise DesktopStorageError("Synthetic corruption")
        return "READY"

    def chunks(self, matter_id):
        if matter_id != "matter-a":
            return []
        return [
            MatterChunk("a0", "matter-a", "a", 1, 0, QUOTE_A),
            MatterChunk("b0", "matter-a", "b", 0, 0, QUOTE_B),
        ]


class FakeLocalModel:
    def __init__(self):
        self.calls = 0

    def available(self):
        return True

    def complete(self, request):
        self.calls += 1
        return ModelResponse(
            provider="ollama", model="local-test-only", metadata={"local": True},
            text=json.dumps(
                {"claims": [
                    _claim(QUOTE_A, "document:a:page:1:chunk:0", "affirmed"),
                    _claim(QUOTE_B, "document:b:page:0:chunk:0", "denied"),
                ]},
                ensure_ascii=False,
            ),
        )


def _matters():
    matters = MatterStore()
    now = datetime.now(timezone.utc)
    for identifier in ("matter-a", "matter-b"):
        matters.create(
            Matter(
                id=identifier, title="Учебное дело " + identifier,
                matter_type=MatterType.CRIMINAL, created_at=now,
                updated_at=now,
            )
        )
    return matters


def _request():
    return ClaimReviewRequest(
        source_document_ids=["a", "b"],
        focus="передача автомобиля по договору №44",
    )


def _report(matters=None, corpus=None, model=None):
    matters = matters or _matters()
    corpus = corpus or FakeCorpus()
    model = model or FakeLocalModel()
    report = ClaimReviewService(matters, corpus, model).inspect("matter-a", _request())
    assert len(report.possible_differences) == 1
    return report


def _ledger(tmp_path, key_byte="a"):
    raw = bytes.fromhex(key_byte * 64)
    return EncryptedClaimDecisionLedger(
        tmp_path / "decisions.sqlite3", derive_decision_ledger_key(raw)
    )


def _decision(pair, status="keep_for_work", note="Проверить оригинал договора"):
    return ReviewDecisionInput(
        candidate_id=pair.id, decision=status, note=note
    )


def test_encrypted_audit_events_append_only_with_reasons_and_restart(tmp_path):
    report = _report()
    pair = report.possible_differences[0]
    store = _ledger(tmp_path)
    first = store.append("matter-a", pair, _decision(pair))
    second = store.append(
        "matter-a", pair, _decision(pair, "dismissed", "Разные обстоятельства"),
    )
    assert first.record_id != second.record_id
    assert [item.decision for item in store.list("matter-a")] == [
        "dismissed", "keep_for_work"
    ] or sorted(item.decision for item in store.list("matter-a")) == [
        "dismissed", "keep_for_work"
    ]
    assert store.list("matter-b") == []
    store.close()

    raw = (tmp_path / "decisions.sqlite3").read_bytes()
    assert "Проверить оригинал договора".encode("utf-8") not in raw
    assert QUOTE_A.encode("utf-8") not in raw
    reopened = _ledger(tmp_path)
    assert len(reopened.list("matter-a")) == 2
    reopened.close()


def test_key_mismatch_and_ciphertext_modification_block_read(tmp_path):
    report = _report()
    pair = report.possible_differences[0]
    store = _ledger(tmp_path)
    stored = store.append("matter-a", pair, _decision(pair))
    store.close()

    with pytest.raises(DesktopStorageError):
        _ledger(tmp_path, key_byte="b")
    connection = sqlite3.connect(tmp_path / "decisions.sqlite3")
    connection.execute(
        "UPDATE review_events SET payload=? WHERE id=?",
        (b"tampered", stored.record_id),
    )
    connection.commit()
    connection.close()
    reopened = _ledger(tmp_path)
    with pytest.raises(DesktopStorageError):
        reopened.list("matter-a")
    reopened.close()


def test_missing_ledger_key_identity_does_not_overwrite_archive(tmp_path):
    (tmp_path / "decisions.sqlite3").write_bytes(b"")
    with pytest.raises(DesktopStorageError):
        _ledger(tmp_path)


def test_reading_another_matter_cannot_disclose_notes(tmp_path):
    report = _report()
    pair = report.possible_differences[0]
    store = _ledger(tmp_path)
    store.append(
        "matter-a", pair, _decision(pair, note="Внутреннее примечание А"),
    )
    assert store.list("matter-b") == []
    store.close()


def test_review_register_docx_is_internal_and_preserves_user_notes(tmp_path):
    report = _report()
    pair = report.possible_differences[0]
    store = _ledger(tmp_path)
    store.append("matter-a", pair, _decision(pair))
    blob = render_review_decisions_docx("Учебное дело", store.list("matter-a"))
    assert blob.startswith(b"PK")
    doc = Document(BytesIO(blob))
    text = "\n".join(p.text for p in doc.paragraphs).replace("\u00a0", " ")
    assert "Проверить оригинал договора" in text
    assert QUOTE_A in text and QUOTE_B in text
    assert "Решение пользователя" in text
    assert "не удостоверяет подлинность" in text
    assert "НЕ ПРОЦЕССУАЛЬНЫЙ ДОКУМЕНТ" in doc.sections[0].footer.paragraphs[0].text
    store.close()


def test_source_recheck_before_decision_and_no_model_call_for_saving(tmp_path, monkeypatch):
    monkeypatch.setenv("JAFAR_RUNTIME_MODE", "desktop")
    token = "synthetic-private-session-token-for-ledger-tests"
    monkeypatch.setenv("JAFAR_DESKTOP_IPC_TOKEN", token)
    matters, corpus, model = _matters(), FakeCorpus(), FakeLocalModel()
    initial = _report(matters, corpus, model)
    assert model.calls == 1
    pair = initial.possible_differences[0]
    store = _ledger(tmp_path)
    app = FastAPI()
    app.middleware("http")(api_auth_middleware)
    app.include_router(build_claim_decision_router(matters, corpus, model, store))
    client = TestClient(app)
    path = "/v1/matters/matter-a/claims/decisions"
    body = {
        "report": initial.model_dump(mode="json"),
        "decision": _decision(pair).model_dump(mode="json"),
    }
    assert client.post(path, json=body).status_code == 401
    headers = {"Authorization": "Bearer " + token}
    response = client.post(path, json=body, headers=headers)
    assert response.status_code == 201, response.text
    assert model.calls == 1
    assert response.json()["decision"] == "keep_for_work"
    listed = client.get(path, headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    word = client.get(path + "/docx", headers=headers)
    assert word.status_code == 200
    assert word.content.startswith(b"PK")
    assert word.headers["cache-control"] == "no-store"
    assert client.get(
        "/v1/matters/matter-b/claims/decisions", headers=headers
    ).json() == []

    body["decision"]["candidate_id"] = "0" * 20
    assert client.post(path, json=body, headers=headers).status_code == 422
    body["decision"]["candidate_id"] = pair.id
    body["report"]["claims"][0]["quote"] = "Выдуманные сведения заявителя"
    assert client.post(path, json=body, headers=headers).status_code == 422
    assert len(client.get(path, headers=headers).json()) == 1
    store.close()


def test_corrupt_source_disallows_decision_without_recording(tmp_path, monkeypatch):
    monkeypatch.setenv("JAFAR_RUNTIME_MODE", "desktop")
    monkeypatch.setenv("JAFAR_DESKTOP_IPC_TOKEN", "fake-long-private-session-token-123")
    matters, corpus, model = _matters(), FakeCorpus(), FakeLocalModel()
    report = _report(matters, corpus, model)
    pair = report.possible_differences[0]
    corpus.corrupt = True
    store = _ledger(tmp_path)
    app = FastAPI()
    app.middleware("http")(api_auth_middleware)
    app.include_router(build_claim_decision_router(matters, corpus, model, store))
    path = "/v1/matters/matter-a/claims/decisions"
    resp = TestClient(app).post(
        path,
        json={
            "report": report.model_dump(mode="json"),
            "decision": _decision(pair).model_dump(mode="json"),
        },
        headers={"Authorization": "Bearer fake-long-private-session-token-123"},
    )
    assert resp.status_code == 409
    assert store.list("matter-a") == []
    store.close()


def test_cloud_mode_has_no_reviewer_ledger_endpoint_data():
    app = FastAPI()
    app.include_router(build_claim_decision_router(_matters(), None, None, None))
    result = TestClient(app).get("/v1/matters/matter-a/claims/decisions")
    assert result.status_code == 404


def test_swift_ui_requires_explicit_user_decision_and_reviewer_note():
    from pathlib import Path

    root = Path(__file__).parents[1]
    view = (root / "apple/JafarApp/JusticiaClaimReviewView.swift").read_text(
        encoding="utf-8"
    )
    api = (root / "apple/JafarApp/JusticiaAPIClient.swift").read_text(
        encoding="utf-8"
    )
    assert "saveClaimReviewDecision(" in api
    assert "/v1/matters/\\(matterID)/claims/decisions" in api
    assert 'Button("Оставить для работы")' in view
    assert 'Button("Отклонить")' in view
    assert 'Button("Нужны документы")' in view
    assert "decisionNote.trimmingCharacters" in view
    assert "savedDecisions.insert(event, at: 0)" in view
    assert "NSSavePanel()" in view
