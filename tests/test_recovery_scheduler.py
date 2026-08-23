from __future__ import annotations

from jafar.document_recovery import RecoveryCandidate
from jafar.recovery_scheduler import ScheduledRecoveryRunner


class Worker:
    def run_once(self, *, limit: int):
        assert limit == 3
        return [RecoveryCandidate("a.pdf", 1), RecoveryCandidate("b.pdf", 2)]


def test_scheduler_tick_reports_claimed_count():
    run = ScheduledRecoveryRunner(Worker()).tick(limit=3)
    assert run.claimed == 2
    assert run.finished_at >= run.started_at
