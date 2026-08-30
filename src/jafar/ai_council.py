from __future__ import annotations

from dataclasses import dataclass

from .cost_scale_control import CostScaleControl, UsageContext
from .matter_intelligence_writer import MatterIntelligenceWriter
from .model_router import (
    ModelProvider,
    ModelRequest,
    ModelResponse,
    ProviderDispatchUncertainError,
)
from .privacy_policy import ProviderPrivacyPolicy
from .supabase_cost_reservations import CostReservationRepository


@dataclass(frozen=True, slots=True)
class CouncilResult:
    responses: tuple[ModelResponse, ...]
    failed_providers: tuple[str, ...]
    disagreements: tuple[str, ...]
    uncertain_providers: tuple[str, ...] = ()
    persistence_status: str = "not_requested"

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
        cost_reservations: CostReservationRepository | None = None,
        intelligence_writer: MatterIntelligenceWriter | None = None,
        owner_id: str = "local-development-user",
    ) -> None:
        self.providers = providers
        self.privacy_policy = privacy_policy or ProviderPrivacyPolicy()
        self.cost_control = cost_control
        self.cost_reservations = cost_reservations
        self.intelligence_writer = intelligence_writer
        self.owner_id = owner_id

    def run(
        self,
        request: ModelRequest,
        *,
        provider_order: tuple[str, ...] | None = None,
        minimum_responses: int = 2,
        matter_id: str | None = None,
        analysis_run_id: str | None = None,
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
        uncertain: list[str] = []
        for key in candidates:
            try:
                responses.append(self._complete_metered(request, key))
            except ProviderDispatchUncertainError:
                failed.append(key)
                uncertain.append(key)
            except Exception:  # noqa: BLE001
                failed.append(key)

        if len(responses) < minimum_responses:
            suffix = f"; uncertain dispatch={','.join(uncertain)}" if uncertain else ""
            raise RuntimeError(
                f"AI Council requires at least {minimum_responses} successful independent responses; "
                f"received {len(responses)}{suffix}"
            )

        disagreements = self._detect_disagreements(tuple(responses))
        result = CouncilResult(
            tuple(responses),
            tuple(failed),
            disagreements,
            tuple(uncertain),
        )
        if self.intelligence_writer is not None:
            effective_matter = matter_id or (request.usage_context.matter_id if request.usage_context else None)
            run_id = analysis_run_id or (request.usage_context.request_id if request.usage_context else None)
            if effective_matter and run_id:
                payload = {
                    "participating_models": [f"{item.provider}:{item.model}" for item in responses],
                    "conclusions": [item.text for item in responses],
                    "evidence_refs": [],
                    "authority_refs": [],
                    "agreements": [],
                    "disagreements": list(disagreements),
                    "unresolved_issues": list(failed) + list(uncertain),
                    "available": True,
                    "verification_state": "requires_review",
                }
                outcome = self.intelligence_writer.write(owner_id=self.owner_id, matter_id=effective_matter, kind="council", payload=payload, analysis_run_id=run_id)
                result = CouncilResult(result.responses, result.failed_providers, result.disagreements, result.uncertain_providers, outcome.status)
        return result

    def _complete_metered(self, request: ModelRequest, provider_key: str) -> ModelResponse:
        context = self._meter_context(request, provider=provider_key)
        reservation_id: str | None = None
        if self.cost_control is not None:
            assert context is not None
            assert request.estimated_cost_usd is not None
            self.cost_control.preflight(
                context,
                estimated_cost_usd=request.estimated_cost_usd,
            )
            if self.cost_reservations is not None:
                reservation = self.cost_reservations.reserve(
                    context=context,
                    estimated_cost_usd=request.estimated_cost_usd,
                    limits=self.cost_control.limits,
                )
                reservation_id = reservation.reservation_id

        try:
            response = self.providers[provider_key].complete(request)
        except Exception as exc:
            # An external call may already have reached the provider. Keeping the reservation
            # active until TTL is safer than making that budget immediately reusable.
            raise ProviderDispatchUncertainError(
                f"Council provider {provider_key!r} dispatch outcome is uncertain"
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
            except Exception as exc:
                raise ProviderDispatchUncertainError(
                    f"Council provider {provider_key!r} accounting outcome is uncertain"
                ) from exc
            if reservation_id is not None:
                self.cost_reservations.settle(reservation_id)
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
