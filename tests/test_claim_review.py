"""Source-verbatim legal claim review tests on synthetic facts only."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace

import pytest
from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jafar.api_auth import api_auth_middleware
from jafar.claim_review import (
    ClaimReviewInvalid, ClaimReviewNotFound,
    ClaimReviewRequest, ClaimReviewService, ClaimReviewTooLarge,
    ClaimReviewUnavailable, render_claim_review_docx,
)
from jafar.claim_review_api import build_claim_review_router
from jafar.domains import MatterType
from jafar.encrypted_sqlite_matter_repository import DesktopStorageError
from jafar.legal_models import Matter
from jafar.matter_rag import MatterChunk
from jafar.matters import MatterStore
from jafar.model_router import ModelResponse


YES = "По договору №44 Иванов передал автомобиль 12.05.2026."
NO = "По договору №44 Иванов не передал автомобиль 12.05.2026."
OTHER = "ДАННЫЕ ЧУЖОГО ДЕЛА ОТСУТСТВУЮТ В ПРОВЕРКЕ."
A = "document:doc-a:page:1:chunk:0"
B = "document:doc-b:page:0:chunk:0"


def _request(ids=None) -> ClaimReviewRequest:
    return ClaimReviewRequest(
        source_document_ids=ids or ["doc-a", "doc-b"],
        focus="передача автомобиля по договору №44",
    )


def _model_claims(first=None, second=None) -> str:
    first = first or {
        "citation": A, "quote": YES,
        "subject": "Иванов", "event_anchor": "договору №44",
        "action_key": "передача автомобиля", "polarity": "affirmed",
    }
    second = second or {
        "citation": B, "quote": NO,
        "subject": "Иванов", "event_anchor": "договору №44",
        "action_key": "передача автомобиля", "polarity": "denied",
    }
    return json.dumps({"claims": [first, second]}, ensure_ascii=False)


class StubCorpus:
    def __init__(self):
        self.data = {
            ("case-a", "doc-a"): SimpleNamespace(
                state="READY", filename="Показания А.pdf",
                provenance=({"page_kind": "pdf_physical", "source_page": 1},),
            ),
            ("case-a", "doc-b"): SimpleNamespace(
                state="READY", filename="Показания Б.txt", provenance=(),
            ),
            ("case-b", "foreign"): SimpleNamespace(
                state="READY", filename="Чужой источник.txt", provenance=(),
            ),
        }
        self.text = {
            "case-a": [
                MatterChunk("a0", "case-a", "doc-a", 1, 0, YES),
                MatterChunk("b0", "case-a", "doc-b", 0, 0, NO),
            ],
            "case-b": [MatterChunk("z0", "case-b", "foreign", 0, 0, OTHER)],
        }
        self.verified = []
        self.corrupt = False

    def get_document(self, matter_id, document_id):
        return self.data.get((matter_id, document_id))

    def verify_document(self, matter_id, document_id):
        self.verified.append((matter_id, document_id))
        if self.corrupt:
            raise DesktopStorageError("Synthetic corrupted ciphertext")
        return "READY"

    def chunks(self, matter_id):
        return list(self.text.get(matter_id, []))


class StubOllama:
    def __init__(self, content=None, *, local=True, available=True):
        self.content = content if content is not None else _model_claims()
        self.local = local
        self.enabled = available
        self.calls = []

    def available(self):
        return self.enabled

    def complete(self, request):
        self.calls.append(request)
        return ModelResponse(
            provider="ollama", model="synthetic-local-model",
            text=self.content, metadata={"local": self.local},
        )


def _matters():
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


def _service(corpus=None, model=None):
    corpus = corpus if corpus is not None else StubCorpus()
    model = model if model is not None else StubOllama()
    return ClaimReviewService(_matters(), corpus, model)


def test_verbatim_quoted_oppositions_are_only_candidates_not_findings():
    corpus = StubCorpus()
    model = StubOllama()
    report = _service(corpus, model).inspect("case-a", _request())
    assert len(report.claims) == 2
    assert len(report.possible_differences) == 1
    assert report.possible_differences[0].status == "possible_difference"
    assert report.claims[0].physical_page == 1
    assert report.claims[1].physical_page is None
    assert corpus.verified == [("case-a", "doc-a"), ("case-a", "doc-b")]
    assert len(model.calls) == 1
    assert model.calls[0].allowed_providers == ("ollama",)
    assert model.calls[0].confidential is True
    assert OTHER not in model.calls[0].prompt
    assert any("гипотез" in w or "предположения" in w for w in report.warnings)


def test_different_event_anchor_does_not_create_false_conflict():
    second = {
        "citation": B, "quote": NO,
        "subject": "Иванов", "event_anchor": "12.05.2026",
        "action_key": "передача автомобиля", "polarity": "denied",
    }
    report = _service(model=StubOllama(_model_claims(second=second))).inspect(
        "case-a", _request()
    )
    assert report.possible_differences == []
    assert len(report.claims) == 2


def test_uncertainty_or_different_action_cannot_form_opposite_pair():
    second = {
        "citation": B, "quote": NO, "subject": "Иванов",
        "event_anchor": "договору №44",
        "action_key": "передача автомобиля", "polarity": "uncertain",
    }
    report = _service(model=StubOllama(_model_claims(second=second))).inspect(
        "case-a", _request()
    )
    assert report.possible_differences == []


@pytest.mark.parametrize(
    "modified",
    [
        {"citation": "document:foreign:page:0:chunk:0"},
        {"quote": "Иванов заявил, что является виновным."},
        {"subject": "Сидоров"},
        {"event_anchor": "договору №99"},
    ],
)
def test_model_cannot_hallucinate_quote_source_actor_or_event(modified):
    first = {
        "citation": A, "quote": YES,
        "subject": "Иванов", "event_anchor": "договору №44",
        "action_key": "передача автомобиля", "polarity": "affirmed",
    }
    first.update(modified)
    model = StubOllama(_model_claims(first=first))
    with pytest.raises(ClaimReviewInvalid):
        _service(model=model).inspect("case-a", _request())


@pytest.mark.parametrize(
    "invalid",
    [
        "not-json",
        json.dumps({"claims": [{"quote": YES}]}),
        json.dumps({"claims": []}, ensure_ascii=False) + " extra",
    ],
)
def test_bad_model_schema_fails_closed(invalid):
    with pytest.raises(ClaimReviewInvalid):
        _service(model=StubOllama(invalid)).inspect("case-a", _request())


def test_nonlocal_model_or_missing_ollama_fails_closed():
    fake_remote = StubOllama(local=False)
    with pytest.raises(ClaimReviewInvalid):
        _service(model=fake_remote).inspect("case-a", _request())
    unavailable = StubOllama(available=False)
    with pytest.raises(ClaimReviewUnavailable):
        _service(model=unavailable).inspect("case-a", _request())
    assert unavailable.calls == []


def test_cross_matter_document_and_missing_case_rejected_before_ai():
    model = StubOllama()
    service = _service(model=model)
    with pytest.raises(ClaimReviewNotFound):
        service.inspect("case-a", _request(["doc-a", "foreign"]))
    with pytest.raises(ClaimReviewNotFound):
        service.inspect("unknown", _request())
    assert model.calls == []


def test_limit_blocks_large_index_without_model_calls():
    corpus = StubCorpus()
    corpus.text["case-a"].append(
        MatterChunk("a1", "case-a", "doc-a", 1, 1, "x" * 800_001)
    )
    model = StubOllama()
    with pytest.raises(ClaimReviewTooLarge):
        _service(corpus, model).inspect("case-a", _request())
    assert model.calls == []


def test_docx_export_revalidates_quotes_and_fingerprints_without_second_ai_call():
    corpus = StubCorpus()
    model = StubOllama()
    service = _service(corpus, model)
    report = service.inspect("case-a", _request())
    validated = service.revalidate_for_export("case-a", report)
    assert len(model.calls) == 1
    blob = render_claim_review_docx(validated)
    assert blob.startswith(b"PK")
    doc = Document(BytesIO(blob))
    text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    assert YES in text and NO in text
    assert "Чужой источник" not in text
    assert "страница не установлена" in text
    assert "физическая страница PDF 1" in text
    assert "возможное различие" in text
    assert doc.styles["Normal"].font.name == "Times New Roman"
    assert "НЕ ПРОВЕРЕН ЮРИСТОМ" in doc.sections[0].footer.paragraphs[0].text


def test_client_cannot_tamper_with_verbatim_quote_or_physical_page():
    service = _service()
    report = service.inspect("case-a", _request())
    modified = report.model_copy(deep=True)
    modified.claims[0].quote = "Неустановленное заявление от третьего лица."
    with pytest.raises(ClaimReviewInvalid):
        service.revalidate_for_export("case-a", modified)
    altered = report.model_copy(deep=True)
    altered.claims[1].physical_page = 1
    with pytest.raises(ClaimReviewInvalid):
        service.revalidate_for_export("case-a", altered)


def test_corrupt_source_blocks_review_and_export():
    corpus = StubCorpus()
    service = _service(corpus)
    report = service.inspect("case-a", _request())
    corpus.corrupt = True
    with pytest.raises(DesktopStorageError):
        service.revalidate_for_export("case-a", report)
    with pytest.raises(DesktopStorageError):
        service.inspect("case-a", _request())


def test_local_authenticated_api_and_forged_word_export(monkeypatch):
    monkeypatch.setenv("JAFAR_RUNTIME_MODE", "desktop")
    monkeypatch.setenv(
        "JAFAR_DESKTOP_IPC_TOKEN", "synthetic-ephemeral-local-token-long-for-testing"
    )
    matters, corpus, model = _matters(), StubCorpus(), StubOllama()
    app = FastAPI()
    app.middleware("http")(api_auth_middleware)
    app.include_router(build_claim_review_router(matters, corpus, model))
    client = TestClient(app)
    base = "/v1/matters/case-a/claims"
    payload = _request().model_dump(mode="json")
    assert client.post(base + "/inspect", json=payload).status_code == 401
    auth = {"Authorization": "Bearer synthetic-ephemeral-local-token-long-for-testing"}
    raw = client.post(base + "/inspect", json=payload, headers=auth)
    assert raw.status_code == 200, raw.text
    report = raw.json()
    assert len(report["possible_differences"]) == 1
    exported = client.post(base + "/docx", json=report, headers=auth)
    assert exported.status_code == 200, exported.text
    assert exported.headers["cache-control"] == "no-store"
    assert exported.content.startswith(b"PK")
    report["claims"][0]["filename"] = "Фальшивое дело.pdf"
    assert client.post(base + "/docx", json=report, headers=auth).status_code == 422
    other = {**payload, "source_document_ids": ["doc-a", "foreign"]}
    result = client.post(base + "/inspect", json=other, headers=auth)
    assert result.status_code == 404
    assert OTHER not in result.text


def test_non_desktop_runtime_does_not_expose_matter_corpus():
    app = FastAPI()
    app.include_router(build_claim_review_router(_matters(), None, None))
    result = TestClient(app).post(
        "/v1/matters/case-a/claims/inspect", json=_request().model_dump(mode="json")
    )
    assert result.status_code == 404


def test_swift_workflow_requires_manual_review_and_scoped_sources():
    from pathlib import Path

    root = Path(__file__).parents[1]
    view = (root / "apple/JafarApp/JusticiaClaimReviewView.swift").read_text(
        encoding="utf-8"
    )
    api = (root / "apple/JafarApp/JusticiaAPIClient.swift").read_text(
        encoding="utf-8"
    )
    shell = (root / "apple/JafarApp/JusticiaRootView.swift").read_text(
        encoding="utf-8"
    )
    assert "JusticiaClaimReviewView(workspace: workspace, apiClient: apiClient)" in shell
    assert "/v1/matters/\\(matterID)/claims/inspect" in api
    assert "/v1/matters/\\(matterID)/claims/docx" in api
    assert "selectedIDs.sorted()" in view
    assert "signature == currentSignature" in view
    assert "NSSavePanel()" in view
    assert "не установленные противоречия" in view
