from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from .action_approval import ActionApprovalRepository, ActionState, payload_fingerprint


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

    Store-backed execution is payload-bound and must atomically claim an approved action before
    invoking a side-effect handler. This prevents two workers from both observing APPROVED and
    sending the same email, filing, message or other external action twice.
    """

    def __init__(
        self,
        store: ActionApprovalRepository | None = None,
        *,
        executor_id: str | None = None,
    ) -> None:
        self.store = store
        self.executor_id = (executor_id or f"executor-{uuid4().hex}").strip()
        if not self.executor_id:
            raise ValueError("executor_id_required")
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
            return ExecutionResult(action_id, "not_found", "Запрос на одобрение не найден.")
        if request.state is ActionState.PROPOSED:
            return ExecutionResult(action_id, "approval_required", "Требуется подтверждение адвоката.")
        if request.state is ActionState.REJECTED:
            return ExecutionResult(action_id, "rejected", "Адвокат отклонил действие.")
        if request.state is ActionState.EXECUTING:
            return ExecutionResult(
                action_id,
                "in_progress",
                "Действие уже выполняется другим исполнительным процессом.",
            )
        if request.state is ActionState.EXECUTED:
            return ExecutionResult(action_id, "invalid_state", "Действие уже выполнено.")
        if request.state is not ActionState.APPROVED:
            return ExecutionResult(action_id, "invalid_state", "Недопустимое состояние действия.")
        if not request.payload_hash:
            return ExecutionResult(
                action_id,
                "payload_binding_required",
                "Одобрение не связано с точным payload; требуется новый запрос на одобрение.",
            )
        try:
            actual_hash = payload_fingerprint(payload)
        except (TypeError, ValueError):
            return ExecutionResult(
                action_id,
                "invalid_payload",
                "Payload действия не может быть детерминированно проверен.",
            )
        if actual_hash != request.payload_hash:
            return ExecutionResult(
                action_id,
                "payload_mismatch",
                "Payload изменён после формирования запроса на одобрение.",
                {"expected_hash": request.payload_hash, "actual_hash": actual_hash},
            )

        handler = self._handlers.get(request.action_type)
        if handler is None:
            return ExecutionResult(action_id, "not_found", "Действие не зарегистрировано.")

        try:
            self.store.claim_for_execution(action_id, executor_id=self.executor_id)
        except ValueError:
            current = self.store.get(action_id)
            if current is not None and current.state is ActionState.EXECUTING:
                return ExecutionResult(
                    action_id,
                    "in_progress",
                    "Действие уже выполняется другим исполнительным процессом.",
                )
            if current is not None and current.state is ActionState.EXECUTED:
                return ExecutionResult(action_id, "invalid_state", "Действие уже выполнено.")
            return ExecutionResult(
                action_id,
                "claim_failed",
                "Не удалось безопасно зафиксировать право на выполнение действия.",
            )

        try:
            result = handler(payload)
        except Exception as exc:
            error_text = str(exc) or exc.__class__.__name__
            try:
                self.store.release_execution_claim(
                    action_id,
                    executor_id=self.executor_id,
                    error=error_text,
                )
            except Exception:
                # Fail closed: if claim release itself cannot be persisted, another worker must not
                # assume the action is safely retryable. Operational recovery can inspect EXECUTING.
                return ExecutionResult(
                    action_id,
                    "execution_recovery_required",
                    "Действие не выполнено; состояние исполнительного claim требует проверки.",
                    {"error": error_text},
                )
            return ExecutionResult(
                action_id,
                "error",
                "Действие не выполнено; одобрение сохранено для контролируемой повторной попытки.",
                {"error": error_text},
            )

        try:
            self.store.mark_executed(action_id, executor_id=self.executor_id)
        except Exception as exc:
            # The side effect may already have happened. Never release the claim here: automatic
            # retry could duplicate an external legal action. Human/ops reconciliation is required.
            return ExecutionResult(
                action_id,
                "execution_recovery_required",
                "Внешнее действие могло быть выполнено, но фиксация результата не завершена.",
                {"error": str(exc) or exc.__class__.__name__},
            )

        data = result if isinstance(result, dict) else {"result": result}
        return ExecutionResult(action_id, "executed", "Действие выполнено.", data)

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
            return ExecutionResult(request.approval_id, "invalid_state", "Запрос уже обработан.")
        if not approved:
            return ExecutionResult(
                request.approval_id,
                "approval_required",
                "Требуется подтверждение адвоката.",
            )
        handler = self._handlers.get(request.action)
        if handler is None:
            return ExecutionResult(request.approval_id, "not_found", "Действие не зарегистрировано.")
        try:
            result = handler(payload)
            data = result if isinstance(result, dict) else {"result": result}
            return ExecutionResult(request.approval_id, "executed", "Действие выполнено.", data)
        except Exception as exc:
            return ExecutionResult(
                request.approval_id,
                "error",
                "Действие не выполнено.",
                {"error": str(exc)},
            )
