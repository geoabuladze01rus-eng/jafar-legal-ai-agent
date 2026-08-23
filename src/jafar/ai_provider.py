from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .domains import DocumentTask, MatterType
from .legal_models import LegalAnalysis


class AIProvider(Protocol):
    def analyze(self, *, text: str, task: DocumentTask, matter_type: MatterType) -> LegalAnalysis: ...


@dataclass(frozen=True)
class AIProviderConfig:
    model: str
    timeout_seconds: float = 60.0


class OpenAILegalAnalyzer:
    """OpenAI adapter boundary; API key is supplied only by runtime environment."""

    def __init__(self, *, config: AIProviderConfig) -> None:
        self.config = config

    def analyze(self, *, text: str, task: DocumentTask, matter_type: MatterType) -> LegalAnalysis:
        raise NotImplementedError("OpenAI SDK wiring belongs to the application runtime.")
