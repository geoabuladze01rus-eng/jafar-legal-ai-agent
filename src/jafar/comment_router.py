from __future__ import annotations

from dataclasses import dataclass

from .editorial_policy import RiskLevel, decide


@dataclass(frozen=True)
class CommentRoute:
    level: RiskLevel
    action: str
    reason: str


def route_comment(text: str) -> CommentRoute:
    decision = decide(text)
    actions = {
        RiskLevel.AUTO: "auto_reply",
        RiskLevel.REVIEW: "queue_for_review",
        RiskLevel.OWNER: "notify_owner",
    }
    return CommentRoute(decision.level, actions[decision.level], decision.reason)
