from __future__ import annotations

from dataclasses import dataclass

from .comment_classifier import CommentIntent
from .comment_response_policy import ResponseDecision


@dataclass(frozen=True)
class SafetyGateResult:
    allowed: bool
    decision: ResponseDecision
    reason: str


BLOCKED_INTENTS = frozenset({CommentIntent.PERSONAL_DATA, CommentIntent.ESCALATE})


def evaluate_response(intent: CommentIntent, decision: ResponseDecision) -> SafetyGateResult:
    if intent in BLOCKED_INTENTS:
        return SafetyGateResult(False, decision, "requires_moderation_or_editor_review")
    if decision.mode not in {"auto_reply", "editor_review", "moderate"}:
        return SafetyGateResult(False, decision, "unknown_response_mode")
    if decision.mode in {"editor_review", "moderate"}:
        return SafetyGateResult(False, decision, "human_review_required")
    return SafetyGateResult(True, decision, "safe_auto_reply")
