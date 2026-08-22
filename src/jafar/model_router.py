from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ModelRequest:
    prompt: str
    task: str
    requires_vision: bool = False
    requires_google_context: bool = False
    verification: bool = False


@dataclass(frozen=True, slots=True)
class ModelResponse:
    provider: str
    model: str
    text: str
    metadata: dict[str, Any]


class ModelProvider(Protocol):
    key: str

    def available(self) -> bool: ...

    def complete(self, request: ModelRequest) -> ModelResponse: ...


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    primary: str
    verifier: str | None = None
    reason: str = ""


class ModelRouter:
    """Provider-agnostic routing policy for Jafar's multimodel architecture."""

    def __init__(self, providers: dict[str, ModelProvider]) -> None:
        self.providers = providers

    def decide(self, request: ModelRequest) -> RoutingDecision:
        if request.requires_vision:
            primary = "gemini"
        elif request.requires_google_context:
            primary = "gemini"
        elif request.task in {"coding", "technical_analysis", "second_opinion"}:
            primary = "deepseek"
        else:
            primary = "openai"

        verifier = None
        if request.verification:
            verifier = "deepseek" if primary != "deepseek" else "openai"

        if not self._available(primary):
            primary = self._first_available(("openai", "gemini", "deepseek", "nano_banana"))
            if primary is None:
                raise RuntimeError("No configured AI provider is available")

        if verifier and not self._available(verifier):
            verifier = None

        return RoutingDecision(primary=primary, verifier=verifier, reason=f"task={request.task}")

    def run(self, request: ModelRequest) -> tuple[ModelResponse, ...]:
        decision = self.decide(request)
        responses = [self.providers[decision.primary].complete(request)]
        if decision.verifier:
            responses.append(self.providers[decision.verifier].complete(request))
        return tuple(responses)

    def _available(self, key: str) -> bool:
        provider = self.providers.get(key)
        return provider is not None and provider.available()

    def _first_available(self, keys: tuple[str, ...]) -> str | None:
        return next((key for key in keys if self._available(key)), None)
