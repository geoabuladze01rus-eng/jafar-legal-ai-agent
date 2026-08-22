from __future__ import annotations

from dataclasses import dataclass
from os import getenv
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class OutboundResult:
    sent: bool
    dry_run: bool
    blocked: bool
    reason: str
    value: object | None = None


class ProductionGuard:
    """Fail-closed guard for outbound Telegram actions.

    Production sending is disabled unless JAFAR_PRODUCTION_SEND=true.
    Dry-run is the default and never invokes the sender callback.
    """

    def __init__(self, production_send: bool | None = None):
        if production_send is None:
            production_send = getenv("JAFAR_PRODUCTION_SEND", "false").lower() == "true"
        self.production_send = production_send

    async def execute(
        self,
        sender: Callable[[], Awaitable[T]],
        *,
        allowed: bool,
    ) -> OutboundResult:
        if not allowed:
            return OutboundResult(False, False, True, "safety_gate_blocked")
        if not self.production_send:
            return OutboundResult(False, True, False, "dry_run")
        value = await sender()
        return OutboundResult(True, False, False, "sent", value)
