from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .command_bus import Command, CommandResult, JafarCommandBus


@dataclass(frozen=True, slots=True)
class ToolRoute:
    name: str
    command: str
    description: str
    requires_approval: bool = True


class JafarToolRouter:
    """Maps high-level agent intents to the unified command bus."""

    def __init__(self, command_bus: JafarCommandBus) -> None:
        self.command_bus = command_bus
        self.routes: dict[str, ToolRoute] = {}

    def register(
        self,
        intent: str,
        command: str,
        description: str,
        *,
        requires_approval: bool = True,
    ) -> None:
        self.routes[intent] = ToolRoute(
            intent,
            command,
            description,
            requires_approval=requires_approval,
        )

    def route(
        self,
        intent: str,
        args: dict[str, Any],
        request_id: str,
        *,
        approved: bool = False,
    ) -> CommandResult:
        route = self.routes.get(intent)
        if route is None:
            return CommandResult("not_found", "Инструмент не найден.", request_id)
        return self.command_bus.dispatch(
            Command(
                route.command,
                args,
                request_id,
                requires_approval=route.requires_approval,
            ),
            approved=approved,
        )
