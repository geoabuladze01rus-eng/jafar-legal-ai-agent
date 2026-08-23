from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .comment_classifier import CommentIntent
from .comment_response_engine import CommentResponseDraft
from .telegram_inbound import TelegramComment


@dataclass(frozen=True)
class CommentAuditRecord:
    update_id: int
    chat_id: str
    message_id: int
    user_id: str | None
    username: str | None
    intent: str
    decision_mode: str
    draft: str
    status: str
    created_at: str


def make_audit_record(comment: TelegramComment, draft: CommentResponseDraft, *, status: str = "draft") -> CommentAuditRecord:
    user_id = comment.user_id if draft.intent is not CommentIntent.PERSONAL_DATA else None
    username = comment.username if draft.intent is not CommentIntent.PERSONAL_DATA else None
    return CommentAuditRecord(
        update_id=comment.update_id,
        chat_id=comment.chat_id,
        message_id=comment.message_id,
        user_id=user_id,
        username=username,
        intent=draft.intent.value,
        decision_mode=draft.decision.mode,
        draft=draft.decision.draft,
        status=status,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
