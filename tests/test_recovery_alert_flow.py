from __future__ import annotations

from datetime import datetime, timezone

from jafar.recovery_alert import RecoveryAlertService
from jafar.recovery_incident import RecoveryIncident


class Store:
    def __init__(self, incident=None):
        self.incident = incident
        self.resolved = 0

    def detect(self):
        return self.incident

    def resolve_open_incidents(self, *, resolved_at):
        self.resolved += 1
        return 1


class Sink:
    def __init__(self):
        self.sent = []

    def send(self, *, incident):
        self.sent.append(incident)


def test_failure_creates_alert_without_resolution():
    incident = RecoveryIncident(7, "worker_stale", "critical", "worker heartbeat is stale")
    store = Store(incident)
    sink = Sink()

    result = RecoveryAlertService(store, sink).run_once(now=datetime.now(timezone.utc))

    assert result.alerted is True
    assert sink.sent == [incident]
    assert store.resolved == 0


def test_recovery_resolves_open_incident():
    store = Store(None)
    sink = Sink()

    result = RecoveryAlertService(store, sink).run_once(now=datetime.now(timezone.utc))

    assert result.alerted is False
    assert result.resolved_count == 1
    assert sink.sent == []
