from datetime import datetime, timezone
from uuid import uuid4

from .legal_models import Deadline, Matter, MatterEvent


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MatterStore:
    """Small in-memory store used until persistent storage is introduced."""

    def __init__(self) -> None:
        self._matters: dict[str, Matter] = {}
        self._events: dict[str, list[MatterEvent]] = {}

    def create(self, matter: Matter) -> Matter:
        self._matters[matter.id] = matter
        self._events.setdefault(matter.id, [])
        return matter

    def get(self, matter_id: str) -> Matter | None:
        return self._matters.get(matter_id)

    def list(self) -> list[Matter]:
        return list(self._matters.values())

    def add_deadlines(self, matter_id: str, deadlines: list[Deadline]) -> Matter | None:
        matter = self.get(matter_id)
        if matter is None:
            return None
        matter.deadlines.extend(deadlines)
        matter.updated_at = utcnow()
        return matter

    def add_event(
        self,
        matter_id: str,
        title: str,
        event_date: datetime,
        description: str | None = None,
        source_document: str | None = None,
    ) -> MatterEvent | None:
        if matter_id not in self._matters:
            return None
        event = MatterEvent(
            id=str(uuid4()),
            matter_id=matter_id,
            title=title,
            event_date=event_date,
            description=description,
            source_document=source_document,
            created_at=utcnow(),
        )
        self._events.setdefault(matter_id, []).append(event)
        return event

    def events(self, matter_id: str) -> list[MatterEvent]:
        return list(self._events.get(matter_id, []))
