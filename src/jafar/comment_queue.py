from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class QueueDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


@dataclass(frozen=True)
class ReviewItem:
    queue_id: int
    text: str
    route: str
    status: str = "queued"


def apply_decision(item: ReviewItem, decision: QueueDecision) -> ReviewItem:
    if item.status != "queued":
        raise ValueError("review item is already resolved")
    return ReviewItem(
        queue_id=item.queue_id,
        text=item.text,
        route=item.route,
        status="approved" if decision == QueueDecision.APPROVE else "rejected",
    )
