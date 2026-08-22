from __future__ import annotations

from dataclasses import dataclass

from .comment_classifier import CommentIntent, classify_comment
from .comment_response_policy import ResponseDecision, build_response


@dataclass(frozen=True)
class CommentResponseDraft:
    intent: CommentIntent
    decision: ResponseDecision


def prepare_response(text: str) -> CommentResponseDraft:
    intent = classify_comment(text)
    return CommentResponseDraft(intent=intent, decision=build_response(intent, text))
