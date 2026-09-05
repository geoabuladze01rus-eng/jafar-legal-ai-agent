from __future__ import annotations

from dataclasses import dataclass

from .memory_command_router import MemoryCommandRoute
from .memory_service import LongTermMemoryService


@dataclass(frozen=True, slots=True)
class MemoryCommandResult:
    intent: str
    message: str
    approval_required: bool = False
    data: dict | None = None


class MemoryCommandExecutor:
    """Execute explicit natural-language memory commands.

    Recall is read-only. Remember/forget mutate persistent state and therefore
    require the caller's explicit approval bit.
    """

    def __init__(self, service: LongTermMemoryService) -> None:
        self.service = service

    def execute(
        self,
        route: MemoryCommandRoute,
        *,
        approved: bool,
        matter_id: str | None = None,
    ) -> MemoryCommandResult:
        if route.intent == "remember":
            if not route.content:
                return MemoryCommandResult("memory_needs_content", "Что именно нужно запомнить?")
            if not approved:
                return MemoryCommandResult(
                    "memory_remember",
                    f"Сохранить в долговременную память: «{route.content}»?",
                    approval_required=True,
                    data={"kind": route.kind.value, "matter_id": matter_id},
                )
            memory = self.service.remember(
                content=route.content,
                kind=route.kind,
                matter_id=matter_id,
                source="natural_language_command",
            )
            return MemoryCommandResult(
                "memory_remember",
                "Запомнил.",
                data={"memory_id": memory.id, "kind": memory.kind.value, "matter_id": memory.matter_id},
            )

        if route.intent == "recall":
            query = route.content or ""
            results = self.service.recall(query, matter_id=matter_id, limit=8, min_similarity=0.20)
            if not results:
                return MemoryCommandResult("memory_recall", "В долговременной памяти ничего подходящего не найдено.", data={"memories": []})
            memories = [
                {
                    "id": item.memory.id,
                    "kind": item.memory.kind.value,
                    "content": item.memory.content,
                    "matter_id": item.memory.matter_id,
                    "similarity": item.similarity,
                }
                for item in results
            ]
            message = "\n".join(f"• {item['content']}" for item in memories)
            return MemoryCommandResult("memory_recall", message, data={"memories": memories})

        if route.intent == "forget":
            if not route.memory_id:
                return MemoryCommandResult("memory_needs_id", "Укажите идентификатор записи памяти, которую нужно удалить.")
            if not approved:
                return MemoryCommandResult(
                    "memory_forget",
                    f"Удалить запись памяти {route.memory_id}?",
                    approval_required=True,
                    data={"memory_id": route.memory_id},
                )
            deleted = self.service.forget(route.memory_id)
            if not deleted:
                return MemoryCommandResult("memory_forget", "Такая запись памяти не найдена.", data={"memory_id": route.memory_id})
            return MemoryCommandResult("memory_forget", "Забыл эту запись.", data={"memory_id": route.memory_id})

        raise ValueError("unsupported memory command")
