from __future__ import annotations

from dataclasses import dataclass

from .comment_audit import CommentAuditRecord, make_audit_record
from .comment_response_engine import CommentResponseDraft, prepare_response
from .telegram_inbound import TelegramComment, normalize_update


@dataclass(frozen=True)
class CommentPipelineResult:
    comment: TelegramComment
    draft: CommentResponseDraft
    audit: CommentAuditRecord


def process_update(update: dict) -> CommentPipelineResult | None:
    comment = normalize_update(update)
    if comment is None:
        return None
    draft = prepare_response(comment.text)
    audit = make_audit_record(comment, draft)
    return CommentPipelineResult(comment=comment, draft=draft, audit=audit)
