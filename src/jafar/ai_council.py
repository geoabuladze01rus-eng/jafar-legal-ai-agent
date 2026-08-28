from __future__ import annotations

from dataclasses import dataclass

from .cost_scale_control import CostScaleControl, UsageContext
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
    """Run independent providers without hiding divergence or bypassing spend controls."""

    DEFAULT_ORDER = ("openai", "qwen", "kimi", "deepseek", "gemini")

    def __init__(
        self,
        providers: dict[str, ModelProvider],
        privacy_policy: ProviderPrivacyPolicy | None = None,
        cost_control: CostScaleControl | None = None,
    ) -> None:
        self.providers = providers
        self.privacy_policy = privacy_policy or ProviderPrivacyPolicy()
        self.cost_control = cost_control

    def run(
        self,
        request: ModelRequest,
        *,
        provider_order: tuple[str, ...] | None = None,
        minimum_responses: int = 2,
    ) -> CouncilResult:
        if minimum_responses < 1:
            raise ValueError("minimum_responses must be at least 1")
        if self.cost_control is not None:
            if request.usage_context is None:
                raise RuntimeError("usage_context_required")
            if request.estimated_cost_usd is None:
                raise RuntimeError("cost_estimate_required")

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
            if key in allowed
            and key in self.providers
            and self.providers[key].available()
            and self._provider_enabled(key)
        )

        responses: list[ModelResponse] = []
        failed: list[str] = []
        for key in candidates:
            try:
                responses.append(self._complete_metered(request, key))
            except Exception:
                failed.append(key)

        if len(responses) < minimum_responses:
            raise RuntimeError(
                f"AI Council requires at least {minimum_responses} successful independent responses; "
                f"received {len(responses)}"
            )

        disagreements = self._detect_disagreements(tuple(responses))
        return CouncilResult(tuple(responses), tuple(failed), disagreements)

    def _complete_metered(self, request: ModelRequest, provider_key: str) -> ModelResponse:
        context = self._meter_context(request, provider=provider_key)
        if self.cost_control is not None:
            assert context is not None
            assert request.estimated_cost_usd is not None
            self.cost_control.preflight(
                context,
                estimated_cost_usd=request.estimated_cost_usd,
            )

        response = self.providers[provider_key].complete(request)
        if self.cost_control is not None:
            assert context is not None
            self.cost_control.meter_response(
                context=context,
                provider=response.provider,
                model=response.model,
                metadata=response.metadata,
            )
        return response

    def _provider_enabled(self, provider_key: str) -> bool:
        return self.cost_control is None or self.cost_control.provider_enabled(provider_key)

    @staticmethod
    def _meter_context(request: ModelRequest, *, provider: str) -> UsageContext | None:
        base = request.usage_context
        if base is None:
            return None
        return UsageContext(
            request_id=f"{base.request_id}:council:{provider}",
            user_id=base.user_id,
            operation=base.operation,
            matter_id=base.matter_id,
        )

    @staticmethod
    def _detect_disagreements(responses: tuple[ModelResponse, ...]) -> tuple[str, ...]:
        normalized = {" ".join(response.text.lower().split()) for response in responses}
        if len(normalized) <= 1:
            return ()
        return (
            "Модели дали различающиеся выводы; расхождения должны быть показаны пользователю и проверены отдельно.",
        )
