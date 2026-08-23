from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass(frozen=True, slots=True)
class VoiceCommand:
    text: str
    normalized_intent: str
    parameters: dict[str, Any]
    confirmation_required: bool = True


class AppleVoiceCommandRouter:
    """Platform-neutral command router for Siri/Shortcuts-style Apple clients."""

    INTENTS: ClassVar[dict[str, str]] = {
        "покажи дела": "list_cases",
        "найди дело": "find_case",
        "проверь компанию": "investigate_entity",
        "создай черновик": "draft_response",
        "напомни": "create_reminder",
        "проанализируй": "analyze_case",
    }

    def parse(self, text: str) -> VoiceCommand:
        normalized = " ".join(text.lower().split())
        for phrase, intent in self.INTENTS.items():
            if phrase in normalized:
                return VoiceCommand(text, intent, {"query": text}, True)
        return VoiceCommand(text, "unknown", {"query": text}, True)
