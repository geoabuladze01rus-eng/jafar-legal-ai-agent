from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

from .ai_provider import OpenAILegalAnalyzer
from .cost_scale_control import CostScaleControl, UsageContext
from .legal_models import AnalysisRequest, LegalAnalysis
from .supabase_cost_reservations import CostReservationRepository


STRUCTURED_ANALYSIS_INPUT_OVERHEAD_TOKENS = 4096


@dataclass(slots=True)
class MeteredStructuredLegalAnalyzer:
    analyzer: OpenAILegalAnalyzer
    cost_control: CostScaleControl
    user_id: str
    reservations: CostReservationRepository | None = None

    def __post_init__(self) -> None:
        if not self.user_id.strip():
            raise ValueError("structured_analysis_user_id_required")

    def estimate_cost(self, request: AnalysisRequest) -> Decimal:
        # Conservative upper bound: GPT-style tokenizers cannot produce more tokens than the
        # UTF-8 byte length of the prompt. Add fixed room for system/task/schema instructions and
        # cap output at the provider configuration's explicit max_output_tokens.
        input_upper = len(request.text.encode("utf-8")) + STRUCTURED_ANALYSIS_INPUT_OVERHEAD_TOKENS
        return self.cost_control.estimate_cost(
            provider=self.analyzer.key,
            model=self.analyzer.config.model,
            input_tokens_upper_bound=input_upper,
            output_tokens_upper_bound=self.analyzer.config.max_output_tokens,
        )

    def analyze(self, request: AnalysisRequest) -> LegalAnalysis:
        if not self.cost_control.provider_enabled(self.analyzer.key):
            raise RuntimeError("structured_analysis_provider_disabled")

        context = UsageContext(
            request_id=f"structured:{uuid4()}",
            user_id=self.user_id.strip(),
            operation="structured_legal_analysis",
            matter_id=request.matter_id,
        )
        estimate = self.estimate_cost(request)
        self.cost_control.preflight(context, estimated_cost_usd=estimate)

        reservation_id: str | None = None
        if self.reservations is not None:
            reservation = self.reservations.reserve(
                context=context,
                estimated_cost_usd=estimate,
                limits=self.cost_control.limits,
            )
            reservation_id = reservation.reservation_id

        try:
            analysis, metadata = self.analyzer.analyze_with_usage(
                text=request.text,
                task=request.task,
                matter_type=request.matter_type,
            )
        except ValueError:
            # Input validation happens before provider dispatch and is safe to release.
            if reservation_id is not None:
                self.reservations.release(reservation_id)
            raise
        except Exception:
            # The provider may have received the request. Keep the reservation active until its
            # TTL rather than understating spend and immediately allowing another expensive call.
            raise

        self.cost_control.meter_response(
            context=context,
            provider=self.analyzer.key,
            model=self.analyzer.config.model,
            metadata=metadata,
        )
        if reservation_id is not None:
            self.reservations.settle(reservation_id)
        return analysis
