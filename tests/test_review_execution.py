from jafar.review_commands import ReviewAction, ReviewCommand
from jafar.review_execution import authorize_and_plan


def test_owner_can_execute_review_command():
    result = authorize_and_plan(ReviewCommand(ReviewAction.APPROVE, 42), 123, 123)
    assert result.accepted is True
    assert result.queue_id == 42


def test_non_owner_cannot_execute_review_command():
    result = authorize_and_plan(ReviewCommand(ReviewAction.APPROVE, 42), 456, 123)
    assert result.accepted is False
    assert result.reason == "owner authorization required"
