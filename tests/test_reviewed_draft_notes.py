"""Selected reviewer comments are internal notes, never allegations in pleadings.

All fixtures and quotes in this test module are synthetic, not client material.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace

import pytest
from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jafar.api_auth import api_auth_middleware
from jafar.domains import MatterType
from jafar.legal_draft_api import build_legal_draft_router
from jafar.legal_draft_service import (
    DraftNotFound, LegalDraftRequest, LegalDraftService,
    render_legal_draft_docx,
)
from jafar.legal_models import Matter
from jafar.matter_rag import MatterChunk
from jafar.matters import MatterStore


QUOTE_A = "По договору №44 Иванов передал автомобиль 12.05.2026."
QUOTE_B = "По договору №44 Иванов не передал автомобиль 12.05.2026."


class FakeCorpus:
    def __init__(self):
        self.documents = {
            ("case-a", "doc-a"): SimpleNamespace(state="READY", filename="Документ А.pdf"),
            ("case-a", "doc-b"): SimpleNamespace(state="READY", filename="Документ Б.txt"),
            ("case-b", "doc-x"): SimpleNamespace(state="READY", filename="Чужое дело.txt"),
        }
        self.texts = {
            "case-a": [
                MatterChunk("a0", "case-a", "doc-a", 1, 0, QUOTE_A),
                MatterChunk("b0", "case-a", "doc-b", 0, 0, QUOTE_B),
            ],
            "case-b": [
                MatterChunk("x0", "case-b", "doc-x", 0, 0, "Чужой конфиденциальный материал"),
            ],
        }
        self.verified = []

    def get_document(self, matter_id, document_id):
        return self.documents.get((matter_id, document_id))

    def verify_document(self, matter_id, document_id):
        self.verified.append((matter_id, document_id))
        return "READY"

    def chunks(self, matter_id):
        return list(self.texts.get(matter_id, []))


def record(
    record_id="review-1", decision="keep_for_work", matter_id="case-a",
    quote_a=QUOTE_A,
):
    return SimpleNamespace(
        record_id=record_id,
        matter_id=matter_id,
        candidate_id="a" * 20,
        decision=decision,
        note="Проверить письменные объяснения и обстоятельства передачи",
        left=SimpleNamespace(
            document_id="doc-a", filename="Документ А.pdf",
            citation="document:doc-a:page:1:chunk:0", quote=quote_a,
        ),
        right=SimpleNamespace(
            document_id="doc-b", filename="Документ Б.txt",
            citation="document:doc-b:page:0:chunk:0", quote=QUOTE_B,
        ),
    )


class FakeReviewLedger:
    def __init__(self, items):
        self.items = items

    def list(self, matter_id):
        return [item for item in self.items if item.matter_id == matter_id]


def matters():
    store = MatterStore()
    now = datetime.now(timezone.utc)
    for case in ("case-a", "case-b"):
        store.create(
            Matter(
                id=case, title="Учебное дело " + case,
                matter_type=MatterType.CRIMINAL,
                created_at=now, updated_at=now,
            )
        )
    return store


def request(review_ids=None, document_ids=None):
    return LegalDraftRequest(
        kind="motion",
        recipient="В учебный районный суд",
        author="От заявителя, статус уточняется",
        position="Заявитель просит проверить приложенные документы.",
        legal_basis="Правовое основание внесено юристом и будет проверено.",
        requested_action="Рассмотреть представленное ходатайство.",
        source_document_ids=document_ids or ["doc-a", "doc-b"],
        review_record_ids=review_ids if review_ids is not None else ["review-1"],
    )


def service(items=None, corpus=None):
    return LegalDraftService(
        matters(), corpus or FakeCorpus(),
        FakeReviewLedger([record()] if items is None else items),
    )


def test_selected_review_note_is_only_in_internal_word_appendix():
    s = service()
    preview = s.preview("case-a", request())
    assert preview.can_export is True
    assert len(preview.review_notes) == 1
    note = preview.review_notes[0]
    assert note.left.document_id == "doc-a"
    assert note.right.document_id == "doc-b"
    assert "не подтверждает достоверность" in " ".join(preview.warnings)
    document = Document(BytesIO(render_legal_draft_docx(preview)))
    body = "\n".join(p.text for p in document.paragraphs).replace("\u00a0", " ")
    external, internal = body.split("СЛУЖЕБНЫЙ ЛИСТ ПРОВЕРКИ ИСТОЧНИКОВ", 1)
    assert "Проверить письменные объяснения" not in external
    assert "Проверить письменные объяснения" in internal
    assert QUOTE_A in internal and QUOTE_B in internal
    assert "СЛУЖЕБНЫЙ" not in external


def test_stale_reviewer_decision_is_blocked_after_newer_dismissal():
    previous = record()
    dismissed = record(record_id="review-2", decision="dismissed")
    with pytest.raises(ValueError, match="superseded"):
        service([dismissed, previous]).preview("case-a", request())


def test_dismissed_decision_not_reintroduced_as_fact():
    with pytest.raises(ValueError, match="dismissed"):
        service([record(decision="dismissed")]).preview("case-a", request())


def test_review_cannot_refer_to_missing_or_unselected_documents():
    with pytest.raises(ValueError, match="not selected"):
        service().preview("case-a", request(document_ids=["doc-a"]))


def test_modified_source_quote_or_filename_does_not_enter_docx():
    with pytest.raises(ValueError, match="quotation failed"):
        service([record(quote_a="Иванов якобы признал вину без основания")]).preview(
            "case-a", request()
        )
    corpus = FakeCorpus()
    corpus.documents[("case-a", "doc-a")].filename = "Изменённый файл.pdf"
    with pytest.raises(ValueError, match="filename has changed"):
        service(corpus=corpus).preview("case-a", request())


def test_unknown_or_foreign_review_id_returns_not_found_without_notes():
    with pytest.raises(DraftNotFound):
        service().preview("case-a", request(["another-id"]))
    foreign = record(matter_id="case-b")
    with pytest.raises(DraftNotFound):
        service([foreign]).preview("case-a", request())


def test_missing_review_ledger_disables_selected_note_without_crash():
    svc = LegalDraftService(matters(), FakeCorpus(), None)
    with pytest.raises(DraftNotFound, match="unavailable"):
        svc.preview("case-a", request())
    assert svc.preview("case-a", request(review_ids=[])).review_notes == []


def test_legacy_json_draft_has_no_selected_reviews_by_default():
    legacy = request(review_ids=[]).model_dump(mode="json")
    legacy.pop("review_record_ids")
    restored = LegalDraftRequest.model_validate(legacy)
    assert restored.review_record_ids == []
    assert restored.model_dump()["review_record_ids"] == []


def test_authenticated_api_rechecks_internal_notes_on_export(monkeypatch):
    monkeypatch.setenv("JAFAR_RUNTIME_MODE", "desktop")
    monkeypatch.setenv(
        "JAFAR_DESKTOP_IPC_TOKEN", "synthetic-very-long-local-token-for-private-drafts"
    )
    corpus = FakeCorpus()
    ledger = FakeReviewLedger([record()])
    app = FastAPI()
    app.middleware("http")(api_auth_middleware)
    app.include_router(build_legal_draft_router(matters(), corpus, None, ledger))
    client = TestClient(app)
    url = "/v1/matters/case-a/drafts"
    payload = request().model_dump(mode="json")
    assert client.post(url + "/preview", json=payload).status_code == 401
    auth = {"Authorization": "Bearer synthetic-very-long-local-token-for-private-drafts"}
    checked = client.post(url + "/preview", json=payload, headers=auth)
    assert checked.status_code == 200, checked.text
    assert len(checked.json()["review_notes"]) == 1
    response = client.post(url + "/export", json=payload, headers=auth)
    assert response.status_code == 200
    assert response.content.startswith(b"PK")
    assert response.headers["cache-control"] == "no-store"

    ledger.items.insert(0, record(record_id="review-2", decision="dismissed"))
    old = client.post(url + "/export", json=payload, headers=auth)
    assert old.status_code == 409
    assert "Проверить письменные" not in old.text


def test_swift_draft_history_backward_compatible_and_manual_review_selection():
    from pathlib import Path

    root = Path(__file__).parents[1]
    swift = (root / "apple/JafarApp/JusticiaDraftComposerView.swift").read_text(
        encoding="utf-8"
    )
    assert 'case reviewRecordIDs = "review_record_ids"' in swift
    assert "decodeIfPresent([String].self, forKey: .reviewRecordIDs) ?? []" in swift
    assert "selectedReviewIDs.sorted()" in swift
    assert "selectedReviewIDs = Set(stored.reviewRecordIDs)" in swift
    assert "latestWorkingDecisions" in swift
    assert "selectedDocIDs.contains(entry.left.documentID)" in swift
    assert "listClaimReviewDecisions" in swift
    assert "только в служебный лист Word" in swift
