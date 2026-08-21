from __future__ import annotations

from .review_auth import is_owner
from .review_commands import ReviewCommand


def authorize_review_command(command: ReviewCommand, sender_id: int | None, owner_id: int | None) -> bool:
    return is_owner(sender_id, owner_id)
