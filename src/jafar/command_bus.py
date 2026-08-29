from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Command:
    name: str
    args: dict[str, Any]
    request_id: str
    requires_approval: bool = True


@dataclass(frozen=True, slots=True)
class CommandResult:
    status: str
    message: str
    request_id: str
    data: dict[str, Any] | None = None


class JafarCommandBus:
    """Single routing point for voice, chat and automation commands."""

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[dict[str, Any]], Any]] = {}

    def register(self, name: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        self._handlers[name] = handler

    def dispatch(self, command: Command, *, approved: bool = False) -> CommandResult:
        if command.requires_approval and not approved:
            return CommandResult("approval_required", "Команда ожидает подтверждения.", command.request_id)
        handler = self._handlers.get(command.name)
        if handler is None:
            return CommandResult("not_found", "Команда не зарегистрирована.", command.request_id)
        try:
            result = handler(command.args)
            data = result if isinstance(result, dict) else {"result": result}
            return CommandResult("completed", "Команда выполнена.", command.request_id, data)
        except Exception as exc:
            return CommandResult("error", "Ошибка выполнения команды.", command.request_id, {"error": str(exc)})
