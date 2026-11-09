"""Tests for a real, scoped, editable Word legal-draft workflow.

All parties, facts and excerpts are synthetic. Never use live client documents here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace

from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jafar.api_auth import api_auth_middleware
from jafar.legal_draft_api import DOCX_MIME, build_legal_draft_router
from jafar.legal_draft_service import LegalDraftRequest, LegalDraftService, render_legal_draft_docx
from jafar.legal_models import Matter
from jafar.domains import MatterType
from jafar.matter_rag import MatterChunk
from jafar.matters import MatterStore


def _matter(matter_id: str) -> Matter:
    now = datetime.now(timezone.utc)
    return Matter(
        id=matter_id,
        title="Учебное дело",
        matter_type=MatterType.CRIMINAL,
        client_name="Тестовый заявитель",
        court_or_authority="Учебный суд",
        case_number="TEST-2026-01",
        created_at=now,
        updated_at=now,
    )


class StubCorpus:
    def __init__(self):
        self._documents = {
            ("matter-a", "doc-a"): SimpleNamespace(
                state="READY", filename="Синтетический протокол.txt"
            ),
            ("matter-b", "doc-b"): SimpleNamespace(
                state="READY", filename="Материалы другого дела.txt"
            ),
        }
        self._chunks = {
            "matter-a": [
                MatterChunk(
                    chunk_id="doc-a:0",
                    matter_id="matter-a",
                    document_id="doc-a",
                    source_page=1,
                    chunk_index=0,
                    content="В тестовом документе указана дата 01.10.2026.",
                ),
                MatterChunk(
                    chunk_id="doc-a:1",
                    matter_id="matter-a",
                    document_id="doc-a",
                    source_page=1,
                    chunk_index=1,
                    content="Второй синтетический фрагмент для проверки.",
                ),
            ],
            "matter-b": [
                MatterChunk(
                    chunk_id="doc-b:0",
                    matter_id="matter-b",
                    document_id="doc-b",
                    source_page=1,
                    chunk_index=0,
                    content="ДАННЫЕ ДРУГОГО ДЕЛА ДОЛЖНЫ БЫТЬ СКРЫТЫ",
                ),
            ],
        }
        self.verified: list[tuple[str, str]] = []

    def get_document(self, matter_id: str, document_id: str):
        return self._documents.get((matter_id, document_id))

    def verify_document(self, matter_id: str, document_id: str) -> str:
        self.verified.append((matter_id, document_id))
        return "READY"

    def chunks(self, matter_id: str) -> list[MatterChunk]:
        return self._chunks.get(matter_id, [])


def _valid_request() -> LegalDraftRequest:
    return LegalDraftRequest(
        kind="motion",
        recipient="В учебный районный суд",
        author="От заявителя, процессуальный статус проверяется",
        position="Заявитель утверждает, что требуется исследовать приложенные материалы.",
        legal_basis="Правовое основание внесено и подлежит проверке юристом.",
        requested_action="Рассмотреть заявленное ходатайство.",
        source_document_ids=["doc-a"],
    )


def _service() -> tuple[LegalDraftService, StubCorpus]:
    matters = MatterStore()
    matters.create(_matter("matter-a"))
    matters.create(_matter("matter-b"))
    corpus = StubCorpus()
    return LegalDraftService(matters, corpus), corpus


def test_grounded_preview_contains_only_own_matter_source_and_no_invented_law():
    service, corpus = _service()
    preview = service.preview("matter-a", _valid_request())
    assert preview.can_export is True
    assert preview.matter_id == "matter-a"
    assert len(preview.evidence) == 2
    assert corpus.verified == [("matter-a", "doc-a")]
    assert all(item.document_id == "doc-a" for item in preview.evidence)
    assert "ДАННЫЕ ДРУГОГО ДЕЛА" not in preview.model_dump_json()
    assert not any("ст. 125" in warning for warning in preview.warnings)
    assert any("не подтверждают номера листов" in warning for warning in preview.warnings)


def test_unrelated_source_document_does_not_leak_across_matters():
    from jafar.legal_draft_service import DraftNotFound

    service, corpus = _service()
    request = _valid_request().model_copy(update={"source_document_ids": ["doc-b"]})
    try:
        service.preview("matter-a", request)
    except DraftNotFound:
        pass
    else:
        raise AssertionError("Cross-Matter source must be rejected")
    assert corpus.verified == []


def test_missing_source_or_required_fields_prevents_docx_generation():
    service, _ = _service()
    empty = _valid_request().model_copy(
        update={"legal_basis": "", "source_document_ids": []}
    )
    preview = service.preview("matter-a", empty)
    assert preview.can_export is False
    assert any("правовые основания" in warning.lower() for warning in preview.warnings)
    try:
        render_legal_draft_docx(preview)
    except ValueError:
        pass
    else:
        raise AssertionError("Incomplete draft must not be exported")


def test_real_docx_has_user_authored_text_sources_and_unsigned_warning():
    service, _ = _service()
    preview = service.preview("matter-a", _valid_request())
    blob = render_legal_draft_docx(preview)
    assert blob.startswith(b"PK")
    document = Document(BytesIO(blob))
    body = "\n".join(p.text for p in document.paragraphs)
    assert "ХОДАТАЙСТВО" in body
    assert "Заявитель утверждает" in body
    assert "Правовое основание внесено" in body
    assert "Рассмотреть заявленное ходатайство" in body
    assert "СЛУЖЕБНЫЙ ЛИСТ" in body
    assert "Синтетический протокол.txt" in body
    assert "ДАННЫЕ ДРУГОГО ДЕЛА" not in body
    assert "НЕ ПОДПИСАН" in document.sections[0].footer.paragraphs[0].text
    assert document.styles["Normal"].font.name == "Times New Roman"


def test_authenticated_local_api_preview_export_and_cross_matter_protection(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JAFAR_API_BEARER_TOKEN", "synthetic-test-token-only")
    service, corpus = _service()
    app = FastAPI()
    app.middleware("http")(api_auth_middleware)
    app.include_router(build_legal_draft_router(service.matters, corpus))
    client = TestClient(app)
    url = "/v1/matters/matter-a/drafts"
    payload = _valid_request().model_dump(mode="json")
    assert client.post(url + "/preview", json=payload).status_code == 401
    headers = {"Authorization": "Bearer synthetic-test-token-only"}
    preview = client.post(url + "/preview", json=payload, headers=headers)
    assert preview.status_code == 200
    assert preview.json()["can_export"]
    export = client.post(url + "/export", json=payload, headers=headers)
    assert export.status_code == 200
    assert export.headers["content-type"].startswith(DOCX_MIME)
    assert export.headers["cache-control"] == "no-store"
    assert export.content.startswith(b"PK")

    wrong = {**payload, "source_document_ids": ["doc-b"]}
    failed = client.post(url + "/export", json=wrong, headers=headers)
    assert failed.status_code == 404
    assert "ДАННЫЕ ДРУГОГО ДЕЛА" not in failed.text
    incomplete = {**payload, "recipient": ""}
    assert client.post(url + "/export", json=incomplete, headers=headers).status_code == 422


def test_cloud_runtime_does_not_expose_local_draft_data():
    matters = MatterStore()
    matters.create(_matter("matter-a"))
    app = FastAPI()
    app.include_router(build_legal_draft_router(matters, None))
    client = TestClient(app)
    response = client.post(
        "/v1/matters/matter-a/drafts/preview",
        json=_valid_request().model_dump(mode="json"),
    )
    assert response.status_code == 404


def test_swift_export_uses_scoped_authenticated_client_and_manual_save():
    from pathlib import Path

    root = Path(__file__).parents[1]
    api = (root / "apple/JafarApp/JusticiaAPIClient.swift").read_text(encoding="utf-8")
    shell = (root / "apple/JafarApp/JusticiaRootView.swift").read_text(encoding="utf-8")
    view = (root / "apple/JafarApp/JusticiaDraftComposerView.swift").read_text(encoding="utf-8")
    assert "/v1/matters/\\(matterID)/drafts/preview" in api
    assert "/v1/matters/\\(matterID)/drafts/export" in api
    assert 'urlRequest.setValue("Bearer \\(token)"' in api
    assert "JusticiaDraftComposerView(workspace: workspace, apiClient: apiClient)" in shell
    assert "selectedDocIDs.sorted()" in view
    assert "NSSavePanel()" in view
    assert 'Button("Создать дело")' not in view
    assert "onChange(of: inputSignature)" in view
