"""Synthetic acceptance tests for local-only, citation-validated drafting assistance."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jafar.domains import MatterType
from jafar.legal_draft_api import build_legal_draft_router
from jafar.legal_draft_service import (
    LegalDraftEvidence,
    LegalDraftPreview,
    LegalDraftRequest,
)
from jafar.legal_draft_suggestions import (
    DraftSuggestionError,
    DraftSuggestionUnavailable,
    suggest_draft_position,
)
from jafar.legal_models import Matter
from jafar.matter_rag import MatterChunk
from jafar.matters import MatterStore
from jafar.model_router import ModelResponse


CITATION = "document:doc-local:page:1:chunk:0"
FOREIGN = "document:doc-foreign:page:1:chunk:0"


def request() -> LegalDraftRequest:
    return LegalDraftRequest(
        kind="motion",
        position="Прошу проверить дату подачи заявления.",
        requested_action="Истребовать документ.",
        source_document_ids=["doc-local"],
    )


def preview() -> LegalDraftPreview:
    return LegalDraftPreview(
        kind="motion", title="ХОДАТАЙСТВО", matter_id="own-matter",
        matter_title="Учебное дело", case_number=None, recipient="", author="",
        position="Прошу проверить дату подачи заявления.", legal_basis="",
        requested_action="Истребовать документ.",
        evidence=[
            LegalDraftEvidence(
                document_id="doc-local", filename="Учебный документ.txt",
                chunk_index=0, citation=CITATION,
                excerpt="По заявлению указана дата 05.09.2026.",
            )
        ],
        warnings=[], can_export=False,
    )


class FakeLocalOllama:
    def __init__(self, content: str, *, enabled: bool = True, local: bool = True):
        self.content = content
        self.enabled = enabled
        self.local = local
        self.requests = []

    def available(self) -> bool:
        return self.enabled

    def complete(self, model_request) -> ModelResponse:
        self.requests.append(model_request)
        return ModelResponse(
            provider="ollama", model="qwen3:4b", text=self.content,
            metadata={"local": self.local},
        )


def response(*, citation: str = CITATION, text: str = "Из документа следует указанная дата.") -> str:
    return json.dumps(
        {"proposed_position": text, "citations": [citation], "points_to_verify": ["Сверить оригинал"]},
        ensure_ascii=False,
    )


def test_local_suggestion_validates_selected_citations_and_is_review_only():
    model = FakeLocalOllama(response())
    result = suggest_draft_position(draft=request(), preview=preview(), model=model)
    assert result.local_only
    assert result.citations == [CITATION]
    assert any("проверяет юрист" in item for item in result.points_to_verify)
    assert len(model.requests) == 1
    assert model.requests[0].allowed_providers == ("ollama",)
    assert model.requests[0].confidential is True


@pytest.mark.parametrize(
    "invalid_text",
    [
        response(citation=FOREIGN),
        response(text="Ссылка document:doc-foreign:page:1:chunk:0 подтверждает дату."),
        "not json",
        json.dumps({"proposed_position": "Без цитат", "citations": []}),
    ],
)
def test_invalid_or_cross_matter_suggestions_fail_closed(invalid_text):
    with pytest.raises(DraftSuggestionError):
        suggest_draft_position(
            draft=request(), preview=preview(),
            model=FakeLocalOllama(invalid_text),
        )


def test_unavailable_local_model_never_falls_back_to_cloud():
    model = FakeLocalOllama(response(), enabled=False)
    with pytest.raises(DraftSuggestionUnavailable):
        suggest_draft_position(draft=request(), preview=preview(), model=model)
    assert not model.requests


def test_claimed_remote_provider_cannot_be_used_as_local_suggestion():
    model = FakeLocalOllama(response(), local=False)
    with pytest.raises(DraftSuggestionError):
        suggest_draft_position(draft=request(), preview=preview(), model=model)


class StubCorpus:
    def get_document(self, matter_id, document_id):
        if (matter_id, document_id) == ("own-matter", "doc-local"):
            return SimpleNamespace(state="READY", filename="Учебный документ.txt")
        return None

    def verify_document(self, matter_id, document_id):
        if (matter_id, document_id) != ("own-matter", "doc-local"):
            raise RuntimeError("Unexpected document")
        return "READY"

    def chunks(self, matter_id):
        if matter_id != "own-matter":
            return []
        return [
            MatterChunk(
                chunk_id="doc-local:0", matter_id="own-matter",
                document_id="doc-local", source_page=1, chunk_index=0,
                content="По заявлению указана дата 05.09.2026.",
            )
        ]


def test_local_api_suggestion_requires_valid_sources_and_ollama():
    matters = MatterStore()
    now = datetime.now(timezone.utc)
    matters.create(
        Matter(
            id="own-matter", title="Учебное дело",
            matter_type=MatterType.CRIMINAL, created_at=now, updated_at=now,
        )
    )
    model = FakeLocalOllama(response())
    app = FastAPI()
    app.include_router(build_legal_draft_router(matters, StubCorpus(), model))
    client = TestClient(app)
    payload = request().model_dump(mode="json")
    url = "/v1/matters/own-matter/drafts/suggest"

    good = client.post(url, json=payload)
    assert good.status_code == 200
    assert good.json()["proposed_position"]
    assert good.json()["citations"] == [CITATION]

    other = client.post(url, json={**payload, "source_document_ids": ["doc-foreign"]})
    assert other.status_code == 404

    missing = client.post(url, json={**payload, "source_document_ids": []})
    assert missing.status_code == 422

    unavailable_app = FastAPI()
    unavailable_app.include_router(build_legal_draft_router(matters, StubCorpus(), None))
    assert TestClient(unavailable_app).post(url, json=payload).status_code == 503


def test_swift_suggestions_require_explicit_insert_and_run_on_current_matter():
    from pathlib import Path

    root = Path(__file__).parents[1]
    view = (root / "apple/JafarApp/JusticiaDraftComposerView.swift").read_text(encoding="utf-8")
    api = (root / "apple/JafarApp/JusticiaAPIClient.swift").read_text(encoding="utf-8")
    assert "/v1/matters/\\(matterID)/drafts/suggest" in api
    assert "suggestDraft(matterID: matterID, draft: draft)" in view
    assert "Предложение локального ИИ" in view
    assert "Вставить предложенную позицию для редактирования" in view
    assert "signature == inputSignature" in view
    assert "position = aiSuggestion.proposedPosition" in view
