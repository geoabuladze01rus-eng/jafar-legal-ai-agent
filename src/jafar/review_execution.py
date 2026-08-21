from __future__ import annotations

from dataclasses import dataclass

from .review_auth import is_owner
from .review_commands import ReviewAction, ReviewCommand


@dataclass(frozen=True)
class ReviewExecution:
    accepted: bool
    action: ReviewAction | None = None
    queue_id: int | None = None
    reason: str | None = None


def authorize_and_plan(command: ReviewCommand, sender_id: int | None, owner_id: int | None) -> ReviewExecution:
    if not is_owner(sender_id, owner_id):
        return ReviewExecution(False, reason="owner authorization required")
    return ReviewExecution(True, action=command.action, queue_id=command.queue_id)
