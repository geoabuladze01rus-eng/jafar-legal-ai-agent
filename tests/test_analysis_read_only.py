from datetime import UTC, date, datetime

from fastapi.testclient import TestClient

from jafar import main
from jafar.document_intake import ExtractedDocument
from jafar.document_workflow import DocumentWorkflow
from jafar.domains import DocumentTask, MatterType
from jafar.legal_analysis import LegalAnalyzer
from jafar.legal_models import Deadline, LegalAnalysis, Matter
from jafar.main import app
from jafar.matters import MatterStore


def _matter() -> Matter:
    now = datetime(2026, 8, 28, 12, tzinfo=UTC)
    return Matter(
        id="matter-read-only",
        title="Проверка read-only анализа",
        matter_type=MatterType.CRIMINAL,
        case_number="123/2026",
        created_at=now,
        updated_at=now,
    )


def test_document_workflow_does_not_persist_event_or_deadline_candidates() -> None:
    store = MatterStore()
    store.create(_matter())
    workflow = DocumentWorkflow(store, LegalAnalyzer())

    result = workflow.process(
        "protocol.txt",
        ExtractedDocument(
            filename="protocol.txt",
            media_type="text/plain",
            text="По делу 123/2026 установлен срок до 31.08.2026.",
        ),
    )

    assert result.match is not None
    assert result.match.matter_id == "matter-read-only"
    assert result.event is None
    assert store.events("matter-read-only") == []
    assert store.get("matter-read-only").deadlines == []


def test_analyze_endpoint_returns_deadline_candidate_without_mutating_matter(monkeypatch) -> None:
    store = MatterStore()
    store.create(_matter())
    monkeypatch.setattr(main, "matter_store", store)
    monkeypatch.setattr(main.settings, "environment", "development")
    monkeypatch.setattr(main.settings, "api_key", None)

    candidate = LegalAnalysis(
        task=DocumentTask.LEGAL_ANALYSIS,
        matter_type=MatterType.CRIMINAL,
        summary="Выявлен кандидат процессуального срока.",
        deadlines=[
            Deadline(
                title="Кандидат срока",
                due_date=date(2026, 8, 31),
                source_text="до 31.08.2026",
                confidence=0.8,
            )
        ],
    )
    monkeypatch.setattr(main, "_analyze", lambda *_args, **_kwargs: candidate)

    response = TestClient(app).post(
        "/v1/analyze",
        json={
            "text": "до 31.08.2026",
            "matter_type": "criminal",
            "matter_id": "matter-read-only",
        },
    )

    assert response.status_code == 200
    assert response.json()["analysis"]["deadlines"][0]["title"] == "Кандидат срока"
    assert store.get("matter-read-only").deadlines == []


def test_analyze_endpoint_still_validates_matter_id_without_mutation(monkeypatch) -> None:
    store = MatterStore()
    monkeypatch.setattr(main, "matter_store", store)
    monkeypatch.setattr(main.settings, "environment", "development")
    monkeypatch.setattr(main.settings, "api_key", None)

    response = TestClient(app).post(
        "/v1/analyze",
        json={
            "text": "текст документа",
            "matter_id": "missing-matter",
        },
    )

    assert response.status_code == 404
