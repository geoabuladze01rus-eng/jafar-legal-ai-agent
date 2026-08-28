from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .action_approval import ActionApprovalRepository, ActionState


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
    """Approval-first execution boundary for externally visible side effects.

    When an auditable approval repository is configured, a caller-provided boolean can never
    grant permission. The service reads persisted lawyer state and marks the action executed
    only after the registered handler completes successfully.
    """

    def __init__(self, store: ActionApprovalRepository | None = None) -> None:
        self.store = store
        self._handlers: dict[str, Callable[[dict[str, Any]], Any]] = {}

    def register(self, action: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        self._handlers[action] = handler

    def execute_approved(
        self,
        action_id: str,
        payload: dict[str, Any],
    ) -> ExecutionResult:
        if self.store is None:
            return ExecutionResult(
                action_id,
                "approval_store_required",
                "Хранилище решений адвоката не настроено.",
            )
        request = self.store.get(action_id)
        if request is None:
            return ExecutionResult(
                action_id,
                "not_found",
                "Запрос на одобрение не найден.",
            )
        if request.state is ActionState.PROPOSED:
            return ExecutionResult(
                action_id,
                "approval_required",
                "Требуется подтверждение адвоката.",
            )
        if request.state is ActionState.REJECTED:
            return ExecutionResult(
                action_id,
                "rejected",
                "Адвокат отклонил действие.",
            )
        if request.state is ActionState.EXECUTED:
            return ExecutionResult(
                action_id,
                "invalid_state",
                "Действие уже выполнено.",
            )
        if request.state is not ActionState.APPROVED:
            return ExecutionResult(
                action_id,
                "invalid_state",
                "Недопустимое состояние действия.",
            )

        handler = self._handlers.get(request.action_type)
        if handler is None:
            return ExecutionResult(
                action_id,
                "not_found",
                "Действие не зарегистрировано.",
            )
        try:
            result = handler(payload)
        except Exception as exc:
            return ExecutionResult(
                action_id,
                "error",
                "Действие не выполнено.",
                {"error": str(exc)},
            )

        self.store.mark_executed(action_id)
        data = result if isinstance(result, dict) else {"result": result}
        return ExecutionResult(
            action_id,
            "executed",
            "Действие выполнено.",
            data,
        )

    def execute(
        self,
        request: ApprovalRequest,
        payload: dict[str, Any],
        *,
        approved: bool,
    ) -> ExecutionResult:
        """Compatibility path for pre-repository callers.

        New production integrations must configure an approval repository and use
        ``execute_approved``. If a repository is present, this method delegates to persisted
        state and ignores the caller-provided ``approved`` flag.
        """
        if self.store is not None:
            return self.execute_approved(request.approval_id, payload)
        if request.status != "pending":
            return ExecutionResult(
                request.approval_id,
                "invalid_state",
                "Запрос уже обработан.",
            )
        if not approved:
            return ExecutionResult(
                request.approval_id,
                "approval_required",
                "Требуется подтверждение адвоката.",
            )
        handler = self._handlers.get(request.action)
        if handler is None:
            return ExecutionResult(
                request.approval_id,
                "not_found",
                "Действие не зарегистрировано.",
            )
        try:
            result = handler(payload)
            data = result if isinstance(result, dict) else {"result": result}
            return ExecutionResult(
                request.approval_id,
                "executed",
                "Действие выполнено.",
                data,
            )
        except Exception as exc:
            return ExecutionResult(
                request.approval_id,
                "error",
                "Действие не выполнено.",
                {"error": str(exc)},
            )
