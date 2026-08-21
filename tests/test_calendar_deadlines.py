from datetime import datetime, timezone

from jafar.calendar_deadlines import DeadlineGuard


def test_low_confidence_deadline_requires_confirmation():
    deadline = DeadlineGuard().build_candidate(
        title="Проверить срок обжалования",
        due_at=datetime(2026, 8, 25, tzinfo=timezone.utc),
        source="plaud",
        confidence=0.71,
    )
    assert deadline.requires_confirmation is True
    assert len(DeadlineGuard().reminder_windows(deadline)) == 3


def test_high_confidence_deadline_is_not_marked_uncertain():
    deadline = DeadlineGuard().build_candidate(
        title="Судебное заседание",
        due_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        source="calendar",
        confidence=1.0,
    )
    assert deadline.requires_confirmation is False
