from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReviewAction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


@dataclass(frozen=True)
class ReviewCommand:
    action: ReviewAction
    queue_id: int


def parse_review_command(text: str) -> ReviewCommand | None:
    parts = text.strip().split()
    if len(parts) != 3 or parts[0].lower() != "/review":
        return None
    try:
        action = ReviewAction(parts[1].lower())
        queue_id = int(parts[2])
    except (ValueError, KeyError):
        return None
    return ReviewCommand(action, queue_id)
