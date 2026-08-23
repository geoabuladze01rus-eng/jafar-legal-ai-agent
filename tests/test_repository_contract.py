from datetime import datetime, timezone

from jafar.domains import MatterType
from jafar.legal_models import Deadline, Matter
from jafar.matters import MatterStore


def make_matter() -> Matter:
    now = datetime.now(timezone.utc)
    return Matter(id="matter-1", title="Тестовое дело", matter_type=MatterType.CIVIL,
                  client_name="Клиент", opposing_party="Оппонент", court_or_authority="Суд",
                  case_number="А40-1/2026", created_at=now, updated_at=now)


def test_record_document_event_is_atomic_at_repository_boundary():
    repo = MatterStore()
    repo.create(make_matter())
    deadline = Deadline(title="Обжалование", due_date=datetime(2026, 8, 21, tzinfo=timezone.utc), source_text="срок")
    event = repo.record_document_event("matter-1", "Анализ документа", datetime.now(timezone.utc),
                                      document_fingerprint="fp-1", deadlines=[deadline])
    assert event is not None
    assert len(repo.events("matter-1")) == 1
    assert len(repo.get("matter-1").deadlines) == 1


def test_record_document_event_is_idempotent():
    repo = MatterStore()
    repo.create(make_matter())
    now = datetime.now(timezone.utc)
    first = repo.record_document_event("matter-1", "Документ", now, document_fingerprint="fp-1")
    second = repo.record_document_event("matter-1", "Документ", now, document_fingerprint="fp-1")
    assert first is not None
    assert second is not None
    assert second.id == first.id
    assert len(repo.events("matter-1")) == 1
