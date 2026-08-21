from datetime import datetime, timezone

from jafar.scheduler import PublicationQueue, ScheduledPost


def test_approved_due_post_is_returned() -> None:
    queue = PublicationQueue()
    queue.add(
        ScheduledPost(
            post_id="p1",
            text="test",
            publish_at=datetime(2026, 8, 21, 10, tzinfo=timezone.utc),
            approved=True,
        )
    )
    due = queue.due(datetime(2026, 8, 21, 11, tzinfo=timezone.utc))
    assert [post.post_id for post in due] == ["p1"]


def test_unapproved_post_is_not_due() -> None:
    queue = PublicationQueue()
    queue.add(
        ScheduledPost(
            post_id="p2",
            text="test",
            publish_at=datetime(2026, 8, 21, 10, tzinfo=timezone.utc),
            approved=False,
        )
    )
    assert queue.due(datetime(2026, 8, 21, 11, tzinfo=timezone.utc)) == []
