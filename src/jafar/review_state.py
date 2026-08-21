from __future__ import annotations

from datetime import datetime, timezone

from .review_commands import ReviewAction


def resolved_status(action: ReviewAction) -> str:
    return "approved" if action == ReviewAction.APPROVE else "rejected"


def resolution_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
