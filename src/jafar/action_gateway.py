from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Channel(str, Enum):
    EMAIL = "email"
    TELEGRAM = "telegram"
    CALENDAR = "calendar"
    DOCUMENT = "document"
    APPLE = "apple"


@dataclass(frozen=True, slots=True)
class GatewayAction:
    action_id: str
    channel: Channel
    operation: str
    payload: dict[str, Any]
    approval_required: bool = True


@dataclass(frozen=True, slots=True)
class CommandEnvelope:
    command_id: str
    user_id: str
    source_device: str
    text: str
    intent: str | None = None
    arguments: dict[str, Any] | None = None


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

    def prepare_command(self, command: CommandEnvelope) -> GatewayAction:
        return self.prepare(
            action_id=command.command_id,
            channel=Channel.APPLE,
            operation=command.intent or "natural_language_command",
            payload={
                "user_id": command.user_id,
                "source_device": command.source_device,
                "text": command.text,
                "arguments": command.arguments or {},
            },
            approved=False,
        )

    def can_execute(self, action: GatewayAction) -> bool:
        return action.approval_required is False
