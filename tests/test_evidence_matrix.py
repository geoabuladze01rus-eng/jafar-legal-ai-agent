"""Evidence matrix tests use synthetic documents and no live legal files."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace

import pytest
from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from jafar.api_auth import api_auth_middleware
from jafar.domains import MatterType
from jafar.evidence_matrix import (
    EvidenceMatrixNotFound, EvidenceMatrixRequest,
    EvidenceMatrixService, EvidenceMatrixTooLarge,
    render_matrix_docx,
)
from jafar.evidence_matrix_api import build_evidence_matrix_router
from jafar.encrypted_sqlite_matter_repository import DesktopStorageError
from jafar.legal_models import Matter
from jafar.matter_rag import MatterChunk
from jafar.matters import MatterStore


def _matter_store() -> MatterStore:
    store = MatterStore()
    now = datetime.now(timezone.utc)
    for matter_id in ("case-a", "case-b"):
        store.create(
            Matter(
                id=matter_id, title="Учебное дело " + matter_id,
                matter_type=MatterType.CIVIL,
                case_number="TEST-2026",
                created_at=now, updated_at=now,
            )
        )
    return store


class StubCorpus:
    def __init__(self, *, differing: bool = True):
        self.docs = {
            ("case-a", "doc-a"): SimpleNamespace(
                state="READY", filename="Синтетический договор A.txt",
                fingerprint="synthetic-hash-a",
            ),
            ("case-a", "doc-b"): SimpleNamespace(
                state="READY", filename="Синтетический договор B.txt",
                fingerprint="synthetic-hash-b",
            ),
            ("case-b", "other"): SimpleNamespace(
                state="READY", filename="ЗАКРЫТЫЙ ДРУГОЙ МАТЕРИАЛ.txt",
                fingerprint="synthetic-hash-foreign",
            ),
        }
        payment = "2 000 000 руб." if differing else "1 000 000 руб."
        self.data = {
            "case-a": [
                MatterChunk(
                    chunk_id="a0", matter_id="case-a", document_id="doc-a",
                    source_page=1, chunk_index=0,
                    content="Дата заключения договора: 12.04.2025\n"
                            "Сумма договора: 1 000 000 руб.\n"
                            "В тексте упоминается 999999999 рублей без подписи поля.\n",
                ),
                MatterChunk(
                    chunk_id="b0", matter_id="case-a", document_id="doc-b",
                    source_page=1, chunk_index=0,
                    content="Дата договора: 12.04.2025\n"
                            f"Стоимость договора: {payment}\n"
                            "Дата оплаты: 33.13.2026\n",
                ),
            ],
            "case-b": [
                MatterChunk(
                    chunk_id="z0", matter_id="case-b", document_id="other",
                    source_page=1, chunk_index=0,
                    content="Сумма договора: 999 999 999 руб.\n",
                ),
            ],
        }
        self.verified = []
        self.corrupt = False

    def get_document(self, matter_id, document_id):
        return self.docs.get((matter_id, document_id))

    def verify_document(self, matter_id, document_id):
        self.verified.append((matter_id, document_id))
        if self.corrupt:
            raise DesktopStorageError("Synthetic integrity mismatch")
        return "READY"

    def chunks(self, matter_id):
        return list(self.data.get(matter_id, []))


def _request(ids=None):
    return EvidenceMatrixRequest(
        source_document_ids=ids or ["doc-a", "doc-b"],
        comparison_subject="Синтетический договор, сверить реквизиты",
    )


def test_explicit_labels_yield_only_scoped_review_candidates():
    corpus = StubCorpus()
    result = EvidenceMatrixService(_matter_store(), corpus).compare("case-a", _request())
    assert result.matter_id == "case-a"
    assert result.possible_difference_count == 1
    assert len(result.sources) == 2
    assert corpus.verified == [("case-a", "doc-a"), ("case-a", "doc-b")]
    statuses = {x.key: x.status for x in result.comparisons}
    assert statuses["contract_date"] == "same_labelled_value"
    assert statuses["contract_amount"] == "possible_difference"
    assert result.other_values == []
    output = result.model_dump_json()
    assert "999999999" not in output
    assert "ЗАКРЫТЫЙ" not in output
    assert "33.13.2026" not in output
    assert "document:doc-a:page:1:chunk:0" in output
    assert any("не удостоверяют номера страниц" in x for x in result.warnings)


def test_identical_label_values_do_not_assert_complete_consistency():
    result = EvidenceMatrixService(_matter_store(), StubCorpus(differing=False)).compare(
        "case-a", _request()
    )
    assert result.possible_difference_count == 0
    assert all(x.status == "same_labelled_value" for x in result.comparisons)
    assert any("Отсутствие расхождений не доказывает" in warning for warning in result.warnings)


def test_unlabelled_numbers_are_not_interpreted_as_evidence():
    corpus = StubCorpus()
    corpus.data["case-a"] = [
        MatterChunk("a0", "case-a", "doc-a", 1, 0, "Сумма: 123 руб. Дата 01.01.2025."),
        MatterChunk("b0", "case-a", "doc-b", 1, 0, "Протокол от 02.02.2025 на сумму 500 руб."),
    ]
    result = EvidenceMatrixService(_matter_store(), corpus).compare("case-a", _request())
    assert result.comparisons == []
    assert result.other_values == []
    assert any("нет двух источников" in w for w in result.warnings)


def test_multiple_values_inside_one_document_marked_ambiguous():
    corpus = StubCorpus()
    corpus.data["case-a"].append(
        MatterChunk(
            "a1", "case-a", "doc-a", 1, 1,
            "Сумма договора: 9 000 000 руб.",
        )
    )
    result = EvidenceMatrixService(_matter_store(), corpus).compare("case-a", _request())
    amounts = next(x for x in result.comparisons if x.key == "contract_amount")
    assert amounts.status == "ambiguous_within_document"
    assert result.possible_difference_count == 0


def test_cross_matter_selection_and_missing_matter_fail_before_leaking():
    corpus = StubCorpus()
    service = EvidenceMatrixService(_matter_store(), corpus)
    with pytest.raises(EvidenceMatrixNotFound):
        service.compare("case-a", _request(["doc-a", "other"]))
    assert corpus.verified == [("case-a", "doc-a")]
    with pytest.raises(EvidenceMatrixNotFound):
        service.compare("missing", _request())
    assert "ЗАКРЫТЫЙ" not in str(corpus.verified)


def test_duplicate_ids_and_less_than_two_documents_rejected():
    with pytest.raises(ValidationError):
        _request(["doc-a", "doc-a"])
    with pytest.raises(ValidationError):
        _request(["doc-a"])


def test_large_source_fails_closed_not_partially_compared():
    corpus = StubCorpus()
    corpus.data["case-a"].append(
        MatterChunk("a1", "case-a", "doc-a", 1, 1, "a" * 800_001)
    )
    with pytest.raises(EvidenceMatrixTooLarge):
        EvidenceMatrixService(_matter_store(), corpus).compare("case-a", _request())


def test_word_export_contains_sources_review_warnings_and_no_foreign_matter():
    matrix = EvidenceMatrixService(_matter_store(), StubCorpus()).compare("case-a", _request())
    body = render_matrix_docx(matrix)
    assert body.startswith(b"PK")
    document = Document(BytesIO(body))
    content = "\n".join(p.text for p in document.paragraphs)
    assert "СЛУЖЕБНАЯ СПРАВКА" in content
    assert "Синтетический договор A.txt" in content
    assert "Синтетический договор B.txt" in content
    assert "разные значения" in content
    assert "document:doc-a:page:1:chunk:0" in content
    assert "ЗАКРЫТЫЙ" not in content
    assert document.styles["Normal"].font.name == "Times New Roman"
    assert "НЕ ПРОЦЕССУАЛЬНЫЙ ДОКУМЕНТ" in document.sections[0].footer.paragraphs[0].text


def test_local_http_auth_and_docx_and_error_isolation(monkeypatch):
    monkeypatch.setenv("JAFAR_RUNTIME_MODE", "desktop")
    monkeypatch.setenv("JAFAR_DESKTOP_IPC_TOKEN", "synthetic-ephemeral-test-token-long-enough")
    corpus = StubCorpus()
    app = FastAPI()
    app.middleware("http")(api_auth_middleware)
    app.include_router(build_evidence_matrix_router(_matter_store(), corpus))
    client = TestClient(app)
    url = "/v1/matters/case-a/evidence/matrix"
    payload = _request().model_dump(mode="json")
    assert client.post(url, json=payload).status_code == 401
    headers = {"Authorization": "Bearer synthetic-ephemeral-test-token-long-enough"}
    result = client.post(url, json=payload, headers=headers)
    assert result.status_code == 200
    assert result.json()["possible_difference_count"] == 1
    exported = client.post(url + "/docx", json=payload, headers=headers)
    assert exported.status_code == 200
    assert exported.content.startswith(b"PK")
    assert exported.headers["cache-control"] == "no-store"
    wrong = {**payload, "source_document_ids": ["doc-a", "other"]}
    unavailable = client.post(url, json=wrong, headers=headers)
    assert unavailable.status_code == 404
    assert "ЗАКРЫТЫЙ" not in unavailable.text
    corpus.corrupt = True
    assert client.post(url, json=payload, headers=headers).status_code == 409


def test_non_desktop_runtime_has_no_comparison_endpoint_data():
    app = FastAPI()
    app.include_router(build_evidence_matrix_router(_matter_store(), None))
    response = TestClient(app).post(
        "/v1/matters/case-a/evidence/matrix", json=_request().model_dump(mode="json")
    )
    assert response.status_code == 404


def test_swift_workspace_exposes_explicit_matter_scoped_comparison():
    from pathlib import Path

    root = Path(__file__).parents[1]
    view = (root / "apple/JafarApp/JusticiaEvidenceMatrixView.swift").read_text(encoding="utf-8")
    api = (root / "apple/JafarApp/JusticiaAPIClient.swift").read_text(encoding="utf-8")
    shell = (root / "apple/JafarApp/JusticiaRootView.swift").read_text(encoding="utf-8")
    assert "JusticiaEvidenceMatrixView(workspace: workspace, apiClient: apiClient)" in shell
    assert "/v1/matters/\\(matterID)/evidence/matrix" in api
    assert "selectedIDs.sorted()" in view
    assert "2...12" in view
    assert "NSSavePanel()" in view
    assert "signature == currentSignature" in view
    assert "не как установленное противоречие" in view
