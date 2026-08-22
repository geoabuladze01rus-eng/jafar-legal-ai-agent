from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class VoiceIntent:
    intent: str
    confidence: float
    arguments: dict[str, str]
    requires_confirmation: bool = True


class AppleVoiceCommandRouter:
    """Maps Siri/Shortcuts voice phrases to safe Jafar intents."""

    PATTERNS = (
        ("investigate_entity", re.compile(r"(?:проверь|проверить)\s+(?P<entity>.+)", re.I)),
        ("find_case", re.compile(r"(?:найди|покажи)\s+(?:дело\s+)?(?P<case>.+)", re.I)),
        ("create_draft", re.compile(r"(?:создай|подготовь)\s+(?:черновик|ответ)(?:\s+(?P<topic>.+))?", re.I)),
        ("set_reminder", re.compile(r"(?:напомни|поставь напоминание)\s+(?P<task>.+)", re.I)),
    )

    def route(self, phrase: str) -> VoiceIntent:
        normalized = " ".join(phrase.strip().split())
        for intent, pattern in self.PATTERNS:
            match = pattern.fullmatch(normalized)
            if match:
                arguments = {k: v for k, v in match.groupdict().items() if v}
                return VoiceIntent(intent, 0.95, arguments, True)
        return VoiceIntent("unknown", 0.0, {}, True)
