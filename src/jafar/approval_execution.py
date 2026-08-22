from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    approval_id: str
    action: str
    reason: str
    basis: tuple[str, ...] = ()
    status: str = "pending"


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    approval_id: str
    status: str
    message: str
    data: dict[str, Any] | None = None


class ApprovalExecutionService:
    """Approval-first execution boundary for all external side effects."""

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[dict[str, Any]], Any]] = {}

    def register(self, action: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        self._handlers[action] = handler

    def execute(self, request: ApprovalRequest, payload: dict[str, Any], *, approved: bool) -> ExecutionResult:
        if request.status != "pending":
            return ExecutionResult(request.approval_id, "invalid_state", "Запрос уже обработан.")
        if not approved:
            return ExecutionResult(request.approval_id, "approval_required", "Требуется подтверждение адвоката.")
        handler = self._handlers.get(request.action)
        if handler is None:
            return ExecutionResult(request.approval_id, "not_found", "Действие не зарегистрировано.")
        try:
            result = handler(payload)
            return ExecutionResult(request.approval_id, "executed", "Действие выполнено.", result if isinstance(result, dict) else {"result": result})
        except Exception as exc:
            return ExecutionResult(request.approval_id, "error", "Действие не выполнено.", {"error": str(exc)})
