from __future__ import annotations

from dataclasses import dataclass
import re

from .memory_models import MemoryKind


REMEMBER_PREFIXES = (
    "запомни ",
    "джафар, запомни ",
    "джафар запомни ",
    "сохрани в память ",
)
RECALL_MARKERS = (
    "что мы решили",
    "что я просил запомнить",
    "что ты помнишь",
    "напомни что решили",
    "вспомни ",
)
FORGET_PREFIXES = (
    "забудь память ",
    "удали память ",
    "забудь запись ",
)


@dataclass(frozen=True, slots=True)
class MemoryCommandRoute:
    intent: str | None = None
    content: str | None = None
    memory_id: str | None = None
    kind: MemoryKind = MemoryKind.NOTE


class NaturalLanguageMemoryRouter:
    """Conservative explicit router for long-term-memory commands.

    It never infers hidden memories from ordinary conversation. Writes and deletes
    are only recognized when the user explicitly asks to remember or forget.
    """

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.casefold().replace("ё", "е").split())

    def route(self, text: str) -> MemoryCommandRoute:
        normalized = self._normalize(text)

        for prefix in REMEMBER_PREFIXES:
            if normalized.startswith(prefix):
                content = normalized[len(prefix):].strip(" .,:;-")
                if not content:
                    return MemoryCommandRoute(intent="remember")
                return MemoryCommandRoute(
                    intent="remember",
                    content=content,
                    kind=self._kind(content),
                )

        for prefix in FORGET_PREFIXES:
            if normalized.startswith(prefix):
                memory_id = normalized[len(prefix):].strip(" .,:;-")
                return MemoryCommandRoute(intent="forget", memory_id=memory_id or None)

        if any(marker in normalized for marker in RECALL_MARKERS):
            return MemoryCommandRoute(intent="recall", content=text.strip())

        return MemoryCommandRoute()

    @staticmethod
    def _kind(content: str) -> MemoryKind:
        if any(word in content for word in ("предпочитаю", "люблю", "не люблю", "формат", "стиль")):
            return MemoryKind.PREFERENCE
        if any(word in content for word in ("решили", "решение", "договорились", "выбрали")):
            return MemoryKind.DECISION
        if any(word in content for word in ("всегда", "правило", "порядок", "алгоритм", "процесс")):
            return MemoryKind.WORKFLOW
        if re.search(r"\b(дело|номер|дата|суд|клиент|контрагент)\b", content):
            return MemoryKind.FACT
        return MemoryKind.NOTE
