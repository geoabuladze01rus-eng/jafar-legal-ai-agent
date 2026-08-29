from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from .cost_scale_control import CostScaleControl, UsageContext
from .domains import DocumentTask
from .privacy_policy import ProviderPrivacyPolicy
from .supabase_cost_reservations import CostReservationRepository


class ModelControlError(RuntimeError):
    """A privacy/cost/control decision blocked dispatch and must never trigger provider fallback."""


class ProviderDispatchUncertainError(RuntimeError):
    """The external provider may have received/billed the request.

    This error is deliberately non-fallback-safe. Replaying against another provider can create
    duplicate token spend and two competing legal analyses for one logical request.
    """


@dataclass(frozen=True, slots=True)
class ModelRequest:
    prompt: str
    task: str
    requires_vision: bool = False
    requires_google_context: bool = False
    verification: bool = False
    confidential: bool = True
    allowed_providers: tuple[str, ...] | None = None
    usage_context: UsageContext | None = None
    estimated_cost_usd: Decimal | None = None


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
    """Provider-agnostic routing guarded by privacy, budget and provider safety controls."""

    PROVIDER_ORDER = ("openai", "gemini", "deepseek", "qwen", "kimi", "nano_banana")
    VERIFIER_ORDER = ("qwen", "kimi", "deepseek", "gemini", "openai")

    def __init__(
        self,
        providers: dict[str, ModelProvider],
        privacy_policy: ProviderPrivacyPolicy | None = None,
        cost_control: CostScaleControl | None = None,
        cost_reservations: CostReservationRepository | None = None,
    ) -> None:
        self.providers = providers
        self.privacy_policy = privacy_policy or ProviderPrivacyPolicy()
        self.cost_control = cost_control
        self.cost_reservations = cost_reservations

    def decide(self, request: ModelRequest) -> RoutingDecision:
        allowed = set(
            self.privacy_policy.validate(
                confidential=request.confidential,
                requested=request.allowed_providers,
            )
        )
        primary = self._preferred_provider(request)

        # Provider availability can select another provider. Cost-control kill switches cannot:
        # those are explicit policy stops and must fail closed at dispatch instead of silently
        # changing where confidential legal material is sent.
        if primary not in allowed or not self._provider_available(primary):
            primary = self._first_provider_available(
                tuple(key for key in self.PROVIDER_ORDER if key in allowed)
            )
            if primary is None:
                raise RuntimeError("No permitted and available AI provider is available")

        verifier = None
        if request.verification:
            verifier = self._first_provider_available(
                tuple(
                    key
                    for key in self.VERIFIER_ORDER
                    if key in allowed and key != primary
                )
            )
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
                responses.append(
                    self._complete_provider(
                        request,
                        decision.verifier,
                        meter_role="verifier",
                    )
                )
            except (ModelControlError, ProviderDispatchUncertainError):
                raise
            except Exception as exc:
                raise RuntimeError(
                    f"Independent verification provider {decision.verifier!r} failed"
                ) from exc
        return tuple(responses)

    def _preferred_provider(self, request: ModelRequest) -> str:
        if request.requires_vision or request.requires_google_context:
            return "gemini"
        if request.task in {"coding", "technical_analysis"}:
            return "deepseek"
        if request.task == "second_opinion":
            return "qwen"
        if request.task in {"long_context", "case_timeline", "cross_document_analysis"}:
            return "kimi"
        if request.task in {DocumentTask.LEGAL_ANALYSIS.value, DocumentTask.RISK_REVIEW.value}:
            return "openai"
        return "openai"

    def _complete_with_fallback(self, request: ModelRequest, primary: str) -> ModelResponse:
        allowed = set(
            self.privacy_policy.validate(
                confidential=request.confidential,
                requested=request.allowed_providers,
            )
        )
        candidates = (primary,) + tuple(
            key
            for key in self.PROVIDER_ORDER
            if key != primary and key in allowed and self._provider_available(key)
        )
        last_error: Exception | None = None
        for key in candidates:
            if not self._provider_available(key):
                continue
            try:
                response = self._complete_provider(request, key, meter_role="primary")
                if key != primary:
                    metadata = dict(response.metadata)
                    metadata["routing_fallback_from"] = primary
                    return ModelResponse(response.provider, response.model, response.text, metadata)
                return response
            except (ModelControlError, ProviderDispatchUncertainError):
                # Policy/accounting failures are not provider-availability signals. Retrying a
                # different provider would bypass the lawyer's spend/privacy/control boundary.
                raise
            except (RuntimeError, OSError) as exc:
                # Only provider/runtime failures known to be fallback-eligible reach this branch.
                last_error = exc
        raise RuntimeError("All permitted AI providers failed before dispatch") from last_error

    def _complete_provider(
        self,
        request: ModelRequest,
        provider_key: str,
        *,
        meter_role: str,
    ) -> ModelResponse:
        if self.cost_control is not None and not self.cost_control.provider_enabled(provider_key):
            raise ModelControlError(f"Provider {provider_key!r} is disabled by scale control")

        context = self._meter_context(request, role=meter_role, provider=provider_key)
        reservation_id: str | None = None
        if self.cost_control is not None:
            if context is None:
                raise ModelControlError("usage_context_required")
            estimate = request.estimated_cost_usd
            if estimate is None:
                raise ModelControlError("cost_estimate_required")
            try:
                self.cost_control.preflight(context, estimated_cost_usd=estimate)
                if self.cost_reservations is not None:
                    reservation = self.cost_reservations.reserve(
                        context=context,
                        estimated_cost_usd=estimate,
                        limits=self.cost_control.limits,
                    )
                    reservation_id = reservation.reservation_id
            except Exception as exc:
                raise ModelControlError("model_cost_control_blocked") from exc

        # From this point forward the request is entering an external provider boundary. An
        # exception cannot prove that no provider-side work or billing occurred, so reservation
        # release and automatic provider fallback are unsafe.
        try:
            response = self.providers[provider_key].complete(request)
        except Exception as exc:
            raise ProviderDispatchUncertainError(
                f"Provider {provider_key!r} dispatch outcome is uncertain"
            ) from exc

        if self.cost_control is not None:
            assert context is not None
            try:
                self.cost_control.meter_response(
                    context=context,
                    provider=response.provider,
                    model=response.model,
                    metadata=response.metadata,
                )
                if reservation_id is not None:
                    assert self.cost_reservations is not None
                    self.cost_reservations.settle(reservation_id)
            except Exception as exc:
                raise ProviderDispatchUncertainError(
                    f"Provider {provider_key!r} completed but accounting outcome is uncertain"
                ) from exc
        return response

    @staticmethod
    def _meter_context(
        request: ModelRequest,
        *,
        role: str,
        provider: str,
    ) -> UsageContext | None:
        base = request.usage_context
        if base is None:
            return None
        return UsageContext(
            request_id=f"{base.request_id}:{role}:{provider}",
            user_id=base.user_id,
            operation=base.operation,
            matter_id=base.matter_id,
        )

    def _provider_available(self, key: str) -> bool:
        provider = self.providers.get(key)
        return provider is not None and provider.available()

    def _first_provider_available(self, keys: tuple[str, ...]) -> str | None:
        return next((key for key in keys if self._provider_available(key)), None)
