from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from .recovery_incident import RecoveryIncident


class IncidentStore(Protocol):
    def detect(self) -> RecoveryIncident | None: ...
    def resolve_open_incidents(self, *, resolved_at: datetime) -> int: ...


class AlertSink(Protocol):
    def send(self, *, incident: RecoveryIncident) -> None: ...


@dataclass(frozen=True)
class AlertRun:
    incident: RecoveryIncident | None
    alerted: bool
    resolved_count: int


class RecoveryAlertService:
    def __init__(self, store: IncidentStore, sink: AlertSink) -> None:
        self.store = store
        self.sink = sink

    def run_once(self, *, now: datetime) -> AlertRun:
        incident = self.store.detect()
        if incident is not None:
            self.sink.send(incident=incident)
            return AlertRun(incident=incident, alerted=True, resolved_count=0)
        resolved = self.store.resolve_open_incidents(resolved_at=now)
        return AlertRun(incident=None, alerted=False, resolved_count=resolved)
