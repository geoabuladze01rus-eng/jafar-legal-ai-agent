from __future__ import annotations

from dataclasses import dataclass

from .comment_audit import CommentAuditRecord, make_audit_record
from .comment_response_engine import CommentResponseDraft, prepare_response
from .response_safety_gate import SafetyGateResult, evaluate_response
from .telegram_inbound import TelegramComment, normalize_update


@dataclass(frozen=True)
class CommentPipelineResult:
    comment: TelegramComment
    draft: CommentResponseDraft
    safety: SafetyGateResult
    audit: CommentAuditRecord


def process_update(update: dict) -> CommentPipelineResult | None:
    comment = normalize_update(update)
    if comment is None:
        return None

    draft = prepare_response(comment.text)
    safety = evaluate_response(draft.intent, draft.decision)
    audit_status = "approved_for_auto_reply" if safety.allowed else "blocked_for_review"
    audit = make_audit_record(comment, draft, status=audit_status)
    return CommentPipelineResult(comment=comment, draft=draft, safety=safety, audit=audit)
