import pytest

from jafar.review_commands import ReviewAction
from jafar.review_transition import plan_transition


def test_approve_transition_records_owner():
    result = plan_transition(42, ReviewAction.APPROVE, 123)
    assert result.new_status == "approved"
    assert result.resolved_by == 123
    assert result.resolved_at


def test_reject_transition_records_owner():
    result = plan_transition(42, ReviewAction.REJECT, 123)
    assert result.new_status == "rejected"


def test_invalid_ids_are_rejected():
    with pytest.raises(ValueError):
        plan_transition(0, ReviewAction.APPROVE, 123)
    with pytest.raises(ValueError):
        plan_transition(42, ReviewAction.APPROVE, 0)
