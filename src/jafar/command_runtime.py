from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from .command_bus import JafarCommandBus
from .matters import MatterStore
from .tool_router import JafarToolRouter


@dataclass(frozen=True, slots=True)
class CommandRuntimeResult:
    intent: str
    message: str
    request_id: str
    approval_required: bool
    data: dict | None = None


class JafarCommandRuntime:
    """Single command facade shared by HTTP, voice and future chat clients."""

    def __init__(self, matter_store: MatterStore) -> None:
        self.matter_store = matter_store
        self.bus = JafarCommandBus()
        self.router = JafarToolRouter(self.bus)
        self._register_commands()

    def _register_commands(self) -> None:
        self.bus.register("health", lambda _: {"message": "Джафар на связи."})
        self.bus.register("list_matters", self._list_matters)

        self.router.register(
            "health",
            "health",
            "Проверка связи с Джафаром",
            requires_approval=False,
        )
        self.router.register(
            "list_matters",
            "list_matters",
            "Показать открытые дела",
            requires_approval=False,
        )

    def execute(
        self,
        intent: str,
        *,
        request_id: str | None = None,
        approved: bool = False,
    ) -> CommandRuntimeResult:
        request_id = request_id or str(uuid4())
        result = self.router.route(intent, {}, request_id, approved=approved)
        if result.status == "approval_required":
            return CommandRuntimeResult(
                intent=intent,
                message=result.message,
                request_id=request_id,
                approval_required=True,
            )
        if result.status != "completed":
            return CommandRuntimeResult(
                intent=intent,
                message=result.message,
                request_id=request_id,
                approval_required=False,
                data=result.data,
            )

        data = result.data or {}
        return CommandRuntimeResult(
            intent=intent,
            message=str(data.get("message", result.message)),
            request_id=request_id,
            approval_required=False,
            data=data,
        )

    def _list_matters(self, _: dict) -> dict:
        matters = self.matter_store.list_matters()
        if not matters:
            return {
                "message": "Сейчас открытых дел в хранилище нет.",
                "count": 0,
                "matters": [],
            }
        return {
            "message": f"У вас {len(matters)} дел.",
            "count": len(matters),
            "matters": [
                {"id": matter.id, "title": matter.title}
                for matter in matters
            ],
        }
