from datetime import datetime, timezone
from uuid import uuid4

from .legal_models import Deadline, Matter, MatterEvent
from .matter_repository import MatterRepository


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MatterStore(MatterRepository):
    """In-memory repository used for tests and local development."""

    def __init__(self) -> None:
        self._matters: dict[str, Matter] = {}
        self._events: dict[str, list[MatterEvent]] = {}

    def create(self, matter: Matter) -> Matter:
        self._matters[matter.id] = matter
        self._events.setdefault(matter.id, [])
        return matter

    def get(self, matter_id: str) -> Matter | None:
        return self._matters.get(matter_id)

    def list_matters(self) -> list[Matter]:
        return list(self._matters.values())

    def add_deadlines(self, matter_id: str, deadlines: list[Deadline]) -> Matter | None:
        matter = self.get(matter_id)
        if matter is None:
            return None
        existing = {(item.title, item.due_date, item.source_text) for item in matter.deadlines}
        for deadline in deadlines:
            key = (deadline.title, deadline.due_date, deadline.source_text)
            if key not in existing:
                matter.deadlines.append(deadline)
                existing.add(key)
        if deadlines:
            matter.updated_at = utcnow()
        return matter

    def record_document_event(
        self, matter_id: str, title: str, event_date: datetime,
        description: str | None = None, source_document: str | None = None,
        document_fingerprint: str | None = None, deadlines: list[Deadline] | None = None,
    ) -> MatterEvent | None:
        if matter_id not in self._matters:
            return None
        if document_fingerprint:
            existing = self.event_by_fingerprint(matter_id, document_fingerprint)
            if existing is not None:
                return existing
        self.add_deadlines(matter_id, deadlines or [])
        return self.add_event(matter_id, title, event_date, description, source_document, document_fingerprint)

    def add_event(
        self, matter_id: str, title: str, event_date: datetime,
        description: str | None = None, source_document: str | None = None,
        document_fingerprint: str | None = None,
    ) -> MatterEvent | None:
        if matter_id not in self._matters:
            return None
        if document_fingerprint:
            existing = self.event_by_fingerprint(matter_id, document_fingerprint)
            if existing is not None:
                return existing
        event = MatterEvent(id=str(uuid4()), matter_id=matter_id, title=title, event_date=event_date,
                            description=description, source_document=source_document,
                            document_fingerprint=document_fingerprint, created_at=utcnow())
        self._events.setdefault(matter_id, []).append(event)
        self._matters[matter_id].updated_at = utcnow()
        return event

    def event_by_fingerprint(self, matter_id: str, document_fingerprint: str) -> MatterEvent | None:
        for event in self._events.get(matter_id, []):
            if event.document_fingerprint == document_fingerprint:
                return event
        return None

    def events(self, matter_id: str) -> list[MatterEvent]:
        return list(self._events.get(matter_id, []))
