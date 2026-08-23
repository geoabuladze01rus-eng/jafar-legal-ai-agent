from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RecoveryIncident:
    incident_id: int
    incident_type: str
    severity: str
    details: str


class RecoveryIncidentStore(Protocol):
    def detect(self) -> RecoveryIncident | None: ...


class RecoveryIncidentService:
    def __init__(self, store: RecoveryIncidentStore) -> None:
        self.store = store

    def detect(self) -> RecoveryIncident | None:
        return self.store.detect()

    def should_alert(self, incident: RecoveryIncident | None) -> bool:
        return incident is not None and incident.severity in {"warning", "critical"}
