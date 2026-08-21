from datetime import datetime, timezone

from jafar.publication_scheduler import ScheduledPublication, is_due


def test_publication_is_due():
    item = ScheduledPublication(1, "-100", "text", datetime(2026, 8, 21, 10, tzinfo=timezone.utc))
    assert is_due(item, datetime(2026, 8, 21, 10, 1, tzinfo=timezone.utc)) is True


def test_future_publication_is_not_due():
    item = ScheduledPublication(1, "-100", "text", datetime(2026, 8, 21, 12, tzinfo=timezone.utc))
    assert is_due(item, datetime(2026, 8, 21, 10, tzinfo=timezone.utc)) is False
