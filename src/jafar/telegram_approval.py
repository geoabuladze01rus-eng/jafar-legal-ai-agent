from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TelegramInbound:
    chat_id: str
    text: str
    message_id: str
    received_at: str


@dataclass(frozen=True, slots=True)
class TelegramAction:
    action: str
    content: str
    requires_approval: bool = True
    case_id: str | None = None
    metadata: dict[str, Any] | None = None


class TelegramApprovalService:
    """Approval-first boundary for Telegram automation."""

    def classify(self, message: TelegramInbound, *, case_id: str | None = None) -> TelegramAction:
        text = message.text.strip()
        if not text:
            return TelegramAction("ignore", "", True, case_id)
        return TelegramAction(
            action="propose_reply",
            content=text,
            requires_approval=True,
            case_id=case_id,
            metadata={"message_id": message.message_id, "received_at": message.received_at},
        )

    def can_publish(self, action: TelegramAction, approved: bool) -> bool:
        return approved and action.action != "ignore"
