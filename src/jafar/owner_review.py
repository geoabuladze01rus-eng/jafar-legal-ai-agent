from __future__ import annotations

from dataclasses import dataclass

from .comment_queue import ReviewItem


@dataclass(frozen=True)
class OwnerReview:
    queue_id: int
    text: str
    route: str
    approve_command: str
    reject_command: str


def build_owner_review(item: ReviewItem) -> OwnerReview:
    return OwnerReview(
        queue_id=item.queue_id,
        text=item.text,
        route=item.route,
        approve_command=f"/review approve {item.queue_id}",
        reject_command=f"/review reject {item.queue_id}",
    )
