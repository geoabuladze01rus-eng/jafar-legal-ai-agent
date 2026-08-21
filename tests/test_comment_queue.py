import pytest

from jafar.comment_queue import QueueDecision, ReviewItem, apply_decision
from jafar.owner_review import build_owner_review


def test_approve_resolves_queued_item():
    item = ReviewItem(7, "Что делать после обыска?", "queue_for_review")
    resolved = apply_decision(item, QueueDecision.APPROVE)
    assert resolved.status == "approved"


def test_reject_resolves_queued_item():
    item = ReviewItem(8, "текст", "notify_owner")
    resolved = apply_decision(item, QueueDecision.REJECT)
    assert resolved.status == "rejected"


def test_resolved_item_cannot_be_decided_again():
    item = ReviewItem(9, "текст", "queue_for_review", status="approved")
    with pytest.raises(ValueError):
        apply_decision(item, QueueDecision.REJECT)


def test_owner_review_contains_commands():
    review = build_owner_review(ReviewItem(12, "текст", "notify_owner"))
    assert review.approve_command == "/review approve 12"
    assert review.reject_command == "/review reject 12"
