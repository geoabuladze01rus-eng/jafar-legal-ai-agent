from __future__ import annotations

from dataclasses import dataclass
import json
from decimal import Decimal, InvalidOperation
from typing import Any

from .config import Settings
from .cost_scale_control import BudgetLimits, CostLedger, CostScaleControl, ProviderPricing
from .supabase_config import SupabaseSettings, build_supabase_client
from .supabase_cost_ledger import SupabaseCostLedger
from .supabase_cost_reservations import (
    CostReservationRepository,
    SupabaseCostReservationRepository,
)


@dataclass(frozen=True, slots=True)
class CostRuntime:
    """Single composition boundary for metering and atomic spend reservation.

    Production callers should construct this object once and pass both members to every
    ModelRouter / AI Council instance. This prevents a configuration drift where metering is
    enabled but the cross-process reservation gate is accidentally omitted.
    """

    control: CostScaleControl | None
    reservations: CostReservationRepository | None


def validate_production_ai_scale(settings: Settings) -> None:
    """Require explicit commercial safety controls before production startup."""

    if settings.environment.strip().casefold() != "production":
        return
    if not settings.ai_cost_control_enabled:
        raise RuntimeError("Production requires AI cost control")
    if settings.storage_backend.strip().casefold() != "supabase":
        raise RuntimeError("Production AI cost control requires persistent Supabase storage")
    if settings.ai_queue_backend.strip().casefold() != "supabase":
        raise RuntimeError("Production requires durable Supabase AI queue")
    if not (settings.ai_pricing_json or "").strip():
        raise RuntimeError("Production requires reviewed AI_PRICING_JSON")
    if not (settings.ai_pricing_version or "").strip():
        raise RuntimeError("Production requires AI_PRICING_VERSION")
    if len(settings.ai_pricing_version.strip()) > 80:
        raise RuntimeError("AI_PRICING_VERSION must be at most 80 characters")

    ceilings = {
        "AI_COST_PER_REQUEST_USD": settings.ai_cost_per_request_usd,
        "AI_COST_USER_DAILY_USD": settings.ai_cost_user_daily_usd,
        "AI_COST_USER_MONTHLY_USD": settings.ai_cost_user_monthly_usd,
        "AI_COST_MATTER_DAILY_USD": settings.ai_cost_matter_daily_usd,
        "AI_COST_MATTER_MONTHLY_USD": settings.ai_cost_matter_monthly_usd,
        "AI_COST_GLOBAL_DAILY_USD": settings.ai_cost_global_daily_usd,
    }
    missing = [name for name, value in ceilings.items() if value is None or value <= 0]
    if missing:
        raise RuntimeError(
            "Production requires positive AI spend ceilings: " + ", ".join(sorted(missing))
        )

    if settings.ai_cost_per_request_usd > settings.ai_cost_user_daily_usd:
        raise RuntimeError("Per-request AI ceiling cannot exceed per-user daily ceiling")
    if settings.ai_cost_per_request_usd > settings.ai_cost_matter_daily_usd:
        raise RuntimeError("Per-request AI ceiling cannot exceed per-matter daily ceiling")
    if settings.ai_cost_user_daily_usd > settings.ai_cost_user_monthly_usd:
        raise RuntimeError("Per-user daily AI ceiling cannot exceed per-user monthly ceiling")
    if settings.ai_cost_matter_daily_usd > settings.ai_cost_matter_monthly_usd:
        raise RuntimeError("Per-matter daily AI ceiling cannot exceed per-matter monthly ceiling")
    if settings.ai_cost_user_daily_usd > settings.ai_cost_global_daily_usd:
        raise RuntimeError("Per-user daily AI ceiling cannot exceed global daily ceiling")
    if settings.ai_cost_matter_daily_usd > settings.ai_cost_global_daily_usd:
        raise RuntimeError("Per-matter daily AI ceiling cannot exceed global daily ceiling")

    if settings.ai_queue_worker_claim_limit <= 0 or settings.ai_queue_worker_claim_limit > 50:
        raise RuntimeError("Production AI queue worker claim limit must be between 1 and 50")
    if settings.ai_rate_limit_requests <= 0 or settings.ai_rate_limit_requests > 1_000_000:
        raise RuntimeError("Production AI rate-limit requests must be between 1 and 1000000")
    if settings.ai_rate_limit_window_seconds <= 0 or settings.ai_rate_limit_window_seconds > 86_400:
        raise RuntimeError("Production AI rate-limit window must be between 1 and 86400 seconds")

    parse_pricing_catalog(settings.ai_pricing_json)


def _server_supabase() -> tuple[object, str]:
    supabase_settings = SupabaseSettings()
    owner_user_id = supabase_settings.require_owner_user_id()
    client = build_supabase_client(supabase_settings, server=True)
    return client, owner_user_id


def _limits(settings: Settings) -> BudgetLimits:
    return BudgetLimits(
        per_request_usd=settings.ai_cost_per_request_usd,
        per_user_daily_usd=settings.ai_cost_user_daily_usd,
        per_user_monthly_usd=settings.ai_cost_user_monthly_usd,
        per_matter_daily_usd=settings.ai_cost_matter_daily_usd,
        per_matter_monthly_usd=settings.ai_cost_matter_monthly_usd,
        global_daily_usd=settings.ai_cost_global_daily_usd,
    )


def _control(
    settings: Settings,
    *,
    ledger: CostLedger | SupabaseCostLedger,
) -> CostScaleControl:
    return CostScaleControl(
        pricing=parse_pricing_catalog(settings.ai_pricing_json),
        ledger=ledger,
        limits=_limits(settings),
        fail_closed_on_missing_pricing=True,
        pricing_version=(settings.ai_pricing_version or "local-unversioned").strip(),
    )


def build_cost_runtime(settings: Settings) -> CostRuntime:
    """Build the complete cost boundary, sharing one Supabase server client in production."""

    production = settings.environment.strip().casefold() == "production"
    if production:
        validate_production_ai_scale(settings)
    if not settings.ai_cost_control_enabled:
        return CostRuntime(control=None, reservations=None)

    if production:
        client, owner_user_id = _server_supabase()
        control = _control(
            settings,
            ledger=SupabaseCostLedger(client, owner_user_id),
        )
        reservations: CostReservationRepository | None = SupabaseCostReservationRepository(
            client,
            owner_user_id,
        )
        return CostRuntime(control=control, reservations=reservations)

    return CostRuntime(
        control=_control(settings, ledger=CostLedger()),
        reservations=None,
    )


def build_cost_scale_control(settings: Settings) -> CostScaleControl | None:
    """Compatibility accessor; new composition code should prefer ``build_cost_runtime``."""

    return build_cost_runtime(settings).control


def build_cost_reservations(settings: Settings) -> CostReservationRepository | None:
    """Compatibility accessor; new composition code should prefer ``build_cost_runtime``."""

    return build_cost_runtime(settings).reservations


def parse_pricing_catalog(raw: str | None) -> dict[tuple[str, str], ProviderPricing]:
    """Parse reviewed runtime pricing without hard-coding volatile vendor prices."""

    if not raw or not raw.strip():
        raise RuntimeError("AI_PRICING_JSON is required when AI cost control is enabled")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AI_PRICING_JSON must contain valid JSON") from exc
    if not isinstance(data, dict) or not data:
        raise RuntimeError("AI_PRICING_JSON must contain at least one provider")

    result: dict[tuple[str, str], ProviderPricing] = {}
    for provider, models in data.items():
        if not isinstance(provider, str) or not provider.strip() or not isinstance(models, dict):
            raise RuntimeError("AI_PRICING_JSON provider entries are invalid")
        provider_key = provider.strip().casefold()
        for model, rates in models.items():
            if not isinstance(model, str) or not model.strip() or not isinstance(rates, dict):
                raise RuntimeError("AI_PRICING_JSON model entries are invalid")
            key = (provider_key, model.strip())
            if key in result:
                raise RuntimeError("AI_PRICING_JSON contains duplicate normalized pricing keys")
            result[key] = _parse_rates(rates)
    return result


def _parse_rates(rates: dict[str, Any]) -> ProviderPricing:
    unknown = set(rates) - {"input", "cached_input", "output"}
    if unknown:
        raise RuntimeError("AI_PRICING_JSON contains unknown rate fields")
    try:
        input_rate = Decimal(str(rates["input"]))
        output_rate = Decimal(str(rates["output"]))
        cached_raw = rates.get("cached_input")
        cached_rate = Decimal(str(cached_raw)) if cached_raw is not None else None
    except (KeyError, InvalidOperation, ValueError) as exc:
        raise RuntimeError("AI_PRICING_JSON rates must be numeric input/output values") from exc

    values = [input_rate, output_rate]
    if cached_rate is not None:
        values.append(cached_rate)
    if any(value < 0 or not value.is_finite() for value in values):
        raise RuntimeError("AI_PRICING_JSON rates must be finite non-negative values")

    return ProviderPricing(
        input_per_million=input_rate,
        cached_input_per_million=cached_rate,
        output_per_million=output_rate,
    )
