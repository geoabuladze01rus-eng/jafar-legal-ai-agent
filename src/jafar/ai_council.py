from __future__ import annotations

from dataclasses import dataclass

from .model_router import ModelProvider, ModelRequest, ModelResponse
from .privacy_policy import ProviderPrivacyPolicy


@dataclass(frozen=True, slots=True)
class CouncilResult:
    responses: tuple[ModelResponse, ...]
    failed_providers: tuple[str, ...]
    disagreements: tuple[str, ...]

    @property
    def providers(self) -> tuple[str, ...]:
        return tuple(response.provider for response in self.responses)


class AICouncil:
    """Run one request through multiple independent providers without hiding divergence."""

    DEFAULT_ORDER = ("openai", "qwen", "kimi", "deepseek", "gemini")

    def __init__(
        self,
        providers: dict[str, ModelProvider],
        privacy_policy: ProviderPrivacyPolicy | None = None,
    ) -> None:
        self.providers = providers
        self.privacy_policy = privacy_policy or ProviderPrivacyPolicy()

    def run(
        self,
        request: ModelRequest,
        *,
        provider_order: tuple[str, ...] | None = None,
        minimum_responses: int = 2,
    ) -> CouncilResult:
        if minimum_responses < 1:
            raise ValueError("minimum_responses must be at least 1")

        requested = provider_order or self.DEFAULT_ORDER
        allowed = set(
            self.privacy_policy.validate(
                confidential=request.confidential,
                requested=request.allowed_providers,
            )
        )
        candidates = tuple(
            key
            for key in requested
            if key in allowed and key in self.providers and self.providers[key].available()
        )

        responses: list[ModelResponse] = []
        failed: list[str] = []
        for key in candidates:
            try:
                responses.append(self.providers[key].complete(request))
            except Exception:
                failed.append(key)

        if len(responses) < minimum_responses:
            raise RuntimeError(
                f"AI Council requires at least {minimum_responses} successful independent responses; "
                f"received {len(responses)}"
            )

        disagreements = self._detect_disagreements(tuple(responses))
        return CouncilResult(tuple(responses), tuple(failed), disagreements)

    @staticmethod
    def _detect_disagreements(responses: tuple[ModelResponse, ...]) -> tuple[str, ...]:
        normalized = {" ".join(response.text.lower().split()) for response in responses}
        if len(normalized) <= 1:
            return ()
        return (
            "Модели дали различающиеся выводы; расхождения должны быть показаны пользователю и проверены отдельно.",
        )
