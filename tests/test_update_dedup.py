import pytest

from jafar.update_dedup import UpdateDeduplicator


def test_duplicate_update_is_rejected():
    dedup = UpdateDeduplicator()
    assert dedup.accept(10) is True
    assert dedup.accept(10) is False


def test_old_updates_are_evicted_after_capacity():
    dedup = UpdateDeduplicator(max_size=2)
    assert dedup.accept(1) is True
    assert dedup.accept(2) is True
    assert dedup.accept(3) is True
    assert dedup.accept(1) is True


def test_capacity_must_be_positive():
    with pytest.raises(ValueError):
        UpdateDeduplicator(max_size=0)
