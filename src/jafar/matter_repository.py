from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from .legal_models import Deadline, Matter, MatterEvent


class MatterRepository(ABC):
    """Persistence boundary for legal matters and their derived state."""

    @abstractmethod
    def create(self, matter: Matter) -> Matter: ...

    @abstractmethod
    def get(self, matter_id: str) -> Matter | None: ...

    @abstractmethod
    def list_matters(self) -> list[Matter]: ...

    @abstractmethod
    def add_deadlines(self, matter_id: str, deadlines: list[Deadline]) -> Matter | None: ...

    @abstractmethod
    def add_event(
        self,
        matter_id: str,
        title: str,
        event_date: datetime,
        description: str | None = None,
        source_document: str | None = None,
        document_fingerprint: str | None = None,
    ) -> MatterEvent | None: ...

    @abstractmethod
    def event_by_fingerprint(self, matter_id: str, document_fingerprint: str) -> MatterEvent | None: ...

    @abstractmethod
    def events(self, matter_id: str) -> list[MatterEvent]: ...
