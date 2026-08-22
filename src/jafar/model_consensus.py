from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .model_router import ModelRequest, ModelResponse, ModelRouter


@dataclass(frozen=True, slots=True)
class ConsensusResult:
    primary: ModelResponse
    verifier: ModelResponse | None
    consensus: str
    confidence: float
    disagreements: tuple[str, ...]


class ModelConsensus:
    """Conservative multi-model comparison; synthesis remains deterministic."""

    def __init__(self, router: ModelRouter) -> None:
        self.router = router

    def evaluate(self, request: ModelRequest) -> ConsensusResult:
        responses = self.router.run(request)
        primary = responses[0]
        verifier = responses[1] if len(responses) > 1 else None
        if verifier is None:
            return ConsensusResult(primary, None, primary.text, 0.55, ())

        same = self._normalize(primary.text) == self._normalize(verifier.text)
        disagreements: tuple[str, ...] = () if same else ("Модели дали различающиеся ответы; требуется дополнительная проверка.",)
        if same:
            return ConsensusResult(primary, verifier, primary.text, 0.85, disagreements)

        combined = (
            "Основной вывод требует проверки.\n\n"
            f"Основная модель ({primary.provider}): {primary.text}\n\n"
            f"Независимая проверка ({verifier.provider}): {verifier.text}"
        )
        return ConsensusResult(primary, verifier, combined, 0.45, disagreements)

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.lower().split())
