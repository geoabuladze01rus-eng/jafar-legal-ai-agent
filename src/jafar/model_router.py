from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .domains import DocumentTask


@dataclass(frozen=True, slots=True)
class ModelRequest:
    prompt: str
    task: str
    requires_vision: bool = False
    requires_google_context: bool = False
    verification: bool = False
    confidential: bool = True
    allowed_providers: tuple[str, ...] = ("openai",)


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
    """Provider-agnostic routing policy with explicit confidentiality controls."""

    def __init__(self, providers: dict[str, ModelProvider]) -> None:
        self.providers = providers

    def decide(self, request: ModelRequest) -> RoutingDecision:
        allowed = set(request.allowed_providers)
        primary = self._preferred_provider(request)

        if primary not in allowed or not self._available(primary):
            primary = self._first_available(
                tuple(key for key in ("openai", "gemini", "deepseek", "nano_banana") if key in allowed)
            )
            if primary is None:
                raise RuntimeError("No permitted and available AI provider is available")

        verifier = None
        if request.verification:
            verifier_candidates = tuple(
                key for key in ("deepseek", "gemini", "openai")
                if key in allowed and key != primary
            )
            verifier = self._first_available(verifier_candidates)
            if verifier is None:
                raise RuntimeError("Verification requested but no independent permitted provider is available")

        return RoutingDecision(
            primary=primary,
            verifier=verifier,
            reason=f"task={request.task}; confidential={request.confidential}",
        )

    def run(self, request: ModelRequest) -> tuple[ModelResponse, ...]:
        decision = self.decide(request)
        primary = self._complete_with_fallback(request, decision.primary)
        responses = [primary]
        if decision.verifier:
            try:
                responses.append(self.providers[decision.verifier].complete(request))
            except Exception as exc:
                raise RuntimeError(
                    f"Independent verification provider {decision.verifier!r} failed"
                ) from exc
        return tuple(responses)

    def _preferred_provider(self, request: ModelRequest) -> str:
        if request.requires_vision or request.requires_google_context:
            return "gemini"
        if request.task in {"coding", "technical_analysis", "second_opinion"}:
            return "deepseek"
        return "openai"

    def _complete_with_fallback(self, request: ModelRequest, primary: str) -> ModelResponse:
        allowed = set(request.allowed_providers)
        candidates = (primary,) + tuple(
            key
            for key in ("openai", "gemini", "deepseek", "nano_banana")
            if key != primary and key in allowed and self._available(key)
        )
        last_error: Exception | None = None
        for key in candidates:
            try:
                response = self.providers[key].complete(request)
                if key != primary:
                    metadata = dict(response.metadata)
                    metadata["routing_fallback_from"] = primary
                    return ModelResponse(response.provider, response.model, response.text, metadata)
                return response
            except Exception as exc:
                last_error = exc
        raise RuntimeError("All permitted AI providers failed during completion") from last_error

    def _available(self, key: str) -> bool:
        provider = self.providers.get(key)
        return provider is not None and provider.available()

    def _first_available(self, keys: tuple[str, ...]) -> str | None:
        return next((key for key in keys if self._available(key)), None)
