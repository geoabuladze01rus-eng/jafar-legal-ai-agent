from datetime import datetime, timezone

from jafar.document_intake import ExtractedDocument
from jafar.domains import DocumentTask, MatterType
from jafar.legal_analysis import LegalAnalyzer
from jafar.legal_models import Matter
from jafar.document_workflow import DocumentWorkflow
from jafar.matters import MatterStore


def make_matter(
    matter_id: str = "matter-1",
    case_number: str = "А40-12345/2026",
    title: str = "Взыскание задолженности",
) -> Matter:
    now = datetime.now(timezone.utc)
    return Matter(
        id=matter_id,
        title=title,
        matter_type=MatterType.CIVIL,
        client_name="ООО Альфа",
        opposing_party="ООО Бета",
        court_or_authority="Арбитражный суд Москвы",
        case_number=case_number,
        created_at=now,
        updated_at=now,
    )


def test_workflow_matches_analyzes_and_creates_event():
    store = MatterStore()
    store.create(make_matter())
    workflow = DocumentWorkflow(store, LegalAnalyzer())

    result = workflow.process(
        "review.txt",
        ExtractedDocument(
            filename="review.txt",
            media_type="text/plain",
            text="По делу А40-12345/2026 срок обжалования до 21.08.2026.",
        ),
        task=DocumentTask.LEGAL_ANALYSIS,
        matter_type=MatterType.CIVIL,
    )

    assert result.match is not None
    assert result.match.matter_id == "matter-1"
    assert result.event is not None
    assert result.event.matter_id == "matter-1"
    assert len(store.events("matter-1")) == 1
    assert store.get("matter-1").deadlines


def test_workflow_does_not_create_event_for_unresolved_document():
    store = MatterStore()
    store.create(make_matter())
    workflow = DocumentWorkflow(store, LegalAnalyzer())

    result = workflow.process(
        "unknown.txt",
        ExtractedDocument(
            filename="unknown.txt",
            media_type="text/plain",
            text="Общий информационный документ без номера дела и сторон.",
        ),
    )

    assert result.match is None
    assert result.event is None
    assert store.events("matter-1") == []


def test_workflow_does_not_mutate_matter_for_ambiguous_match():
    store = MatterStore()
    store.create(make_matter("matter-1", "А40-12345/2026", "Спор с ООО Альфа"))
    store.create(make_matter("matter-2", "А40-12346/2026", "Спор с ООО Альфа"))
    workflow = DocumentWorkflow(store, LegalAnalyzer())

    result = workflow.process(
        "ambiguous.txt",
        ExtractedDocument(
            filename="ambiguous.txt",
            media_type="text/plain",
            text="Спор с ООО Альфа, номер дела не указан.",
        ),
    )

    assert result.match is None
    assert result.event is None
    assert store.events("matter-1") == []
    assert store.events("matter-2") == []
    assert store.get("matter-1").deadlines == []
    assert store.get("matter-2").deadlines == []


def test_workflow_creates_single_event_per_processing_call():
    store = MatterStore()
    store.create(make_matter())
    workflow = DocumentWorkflow(store, LegalAnalyzer())
    extracted = ExtractedDocument(
        filename="review.txt",
        media_type="text/plain",
        text="По делу А40-12345/2026 срок обжалования до 21.08.2026.",
    )

    first = workflow.process("review.txt", extracted)
    second = workflow.process("review.txt", extracted)

    assert first.event is not None
    assert second.event is not None
    assert len(store.events("matter-1")) == 2
