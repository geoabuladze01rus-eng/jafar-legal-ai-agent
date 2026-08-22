from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ShortcutContract:
    name: str
    intent: str
    input_fields: tuple[str, ...]
    output_type: str
    requires_confirmation: bool = True


class AppleShortcutsContract:
    """Platform-neutral contract for Siri/Apple Shortcuts integration."""

    CONTRACTS = (
        ShortcutContract("Jafar Find Case", "find_case", ("query",), "case_candidates"),
        ShortcutContract("Jafar Investigate Entity", "investigate_entity", ("query",), "entity_report"),
        ShortcutContract("Jafar Analyze Document", "analyze_document", ("document_id",), "legal_analysis"),
        ShortcutContract("Jafar Prepare Draft", "create_draft", ("channel", "topic"), "draft", True),
        ShortcutContract("Jafar Set Reminder", "set_reminder", ("task", "when"), "reminder", True),
    )

    @classmethod
    def get(cls, intent: str) -> ShortcutContract | None:
        return next((item for item in cls.CONTRACTS if item.intent == intent), None)

    @classmethod
    def validate(cls, intent: str, arguments: dict[str, Any]) -> bool:
        contract = cls.get(intent)
        if contract is None:
            return False
        return all(field in arguments and str(arguments[field]).strip() for field in contract.input_fields)
