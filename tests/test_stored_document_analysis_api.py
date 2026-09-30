from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from jafar import main
from jafar.domains import DocumentTask, MatterType
from jafar.legal_analysis import LegalAnalyzer
from jafar.legal_models import Matter
from jafar.main import AnalyzeStoredDocumentRequest, analyze_stored_desktop_document


class FakeMatterStore:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.matter = Matter(
            id="matter-1",
            title="Synthetic matter",
            matter_type=MatterType.CIVIL,
            client_name="Synthetic client",
            case_number="SYN-1",
            created_at=now,
            updated_at=now,
        )

    def get(self, matter_id: str):
        return self.matter if matter_id == self.matter.id else None


class FakeCorpus:
    def __init__(self, missing: bool = False) -> None:
        self.missing = missing
        self.read_calls: list[tuple[str, str]] = []

    def get_document(self, matter_id: str, document_id: str):
        if self.missing or matter_id != "matter-1" or document_id != "doc-1":
            return None
        return SimpleNamespace(filename="synthetic.txt", media_type="text/plain")

    def read_original(self, matter_id: str, document_id: str) -> bytes:
        self.read_calls.append((matter_id, document_id))
        return "Синтетический документ. Срок 01.10.2026. Упоминается договор.".encode()


class FakeWorkflow:
    def __init__(self) -> None:
        self.calls = []

    def process(self, document_name, extracted, task, matter_type, matter_id=None):
        self.calls.append((document_name, task, matter_type, matter_id))
        analysis = LegalAnalyzer().analyze(extracted.text, task, matter_type)
        return SimpleNamespace(analysis=analysis)


def test_stored_document_analysis_reads_only_selected_matter_document(monkeypatch):
    corpus = FakeCorpus()
    workflow = FakeWorkflow()
    monkeypatch.setattr(main, "matter_store", FakeMatterStore())
    monkeypatch.setattr(main, "desktop_corpus_store", corpus)
    monkeypatch.setattr(main, "document_workflow", workflow)

    response = analyze_stored_desktop_document(
        "matter-1",
        "doc-1",
        AnalyzeStoredDocumentRequest(task=DocumentTask.LEGAL_ANALYSIS),
    )

    assert response.matter_id == "matter-1"
    assert response.analysis.task == DocumentTask.LEGAL_ANALYSIS
    assert response.analysis.matter_type == MatterType.CIVIL
    assert corpus.read_calls == [("matter-1", "doc-1")]
    assert workflow.calls == [
        ("synthetic.txt", DocumentTask.LEGAL_ANALYSIS, MatterType.CIVIL, "matter-1")
    ]


def test_stored_document_analysis_rejects_wrong_document_scope(monkeypatch):
    monkeypatch.setattr(main, "matter_store", FakeMatterStore())
    monkeypatch.setattr(main, "desktop_corpus_store", FakeCorpus(missing=True))

    with pytest.raises(HTTPException) as exc:
        analyze_stored_desktop_document(
            "matter-1",
            "other-doc",
            AnalyzeStoredDocumentRequest(task=DocumentTask.RISK_REVIEW),
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Document not found"
