from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .review_commands import ReviewAction


@dataclass(frozen=True)
class ReviewTransition:
    queue_id: int
    new_status: str
    resolved_by: int
    resolved_at: str


def plan_transition(queue_id: int, action: ReviewAction, owner_id: int) -> ReviewTransition:
    if queue_id <= 0:
        raise ValueError("queue_id must be positive")
    if owner_id <= 0:
        raise ValueError("owner_id must be positive")
    status = "approved" if action == ReviewAction.APPROVE else "rejected"
    return ReviewTransition(
        queue_id=queue_id,
        new_status=status,
        resolved_by=owner_id,
        resolved_at=datetime.now(timezone.utc).isoformat(),
    )
