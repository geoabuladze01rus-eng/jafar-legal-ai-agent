from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Channel(str, Enum):
    EMAIL = "email"
    TELEGRAM = "telegram"
    CALENDAR = "calendar"
    DOCUMENT = "document"


@dataclass(frozen=True, slots=True)
class GatewayAction:
    action_id: str
    channel: Channel
    operation: str
    payload: dict[str, Any]
    approval_required: bool = True


class UnifiedActionGateway:
    """Single policy boundary for externally visible Jafar actions."""

    def prepare(self, *, action_id: str, channel: Channel, operation: str, payload: dict[str, Any], approved: bool = False) -> GatewayAction:
        return GatewayAction(
            action_id=action_id,
            channel=channel,
            operation=operation,
            payload=dict(payload),
            approval_required=not approved,
        )

    def can_execute(self, action: GatewayAction) -> bool:
        return action.approval_required is False
