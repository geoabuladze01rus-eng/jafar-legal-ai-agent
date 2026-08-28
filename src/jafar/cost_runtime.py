from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from .config import Settings
from .cost_scale_control import BudgetLimits, CostLedger, CostScaleControl, ProviderPricing
from .supabase_config import SupabaseSettings, build_supabase_client
from .supabase_cost_ledger import SupabaseCostLedger


def build_cost_scale_control(settings: Settings) -> CostScaleControl | None:
    if not settings.ai_cost_control_enabled:
        return None

    pricing = parse_pricing_catalog(settings.ai_pricing_json)
    limits = BudgetLimits(
        per_request_usd=settings.ai_cost_per_request_usd,
        per_user_daily_usd=settings.ai_cost_user_daily_usd,
        per_user_monthly_usd=settings.ai_cost_user_monthly_usd,
        global_daily_usd=settings.ai_cost_global_daily_usd,
    )

    if settings.environment.strip().casefold() == "production":
        if settings.storage_backend.strip().casefold() != "supabase":
            raise RuntimeError("Production AI cost control requires persistent Supabase storage")
        supabase_settings = SupabaseSettings()
        owner_user_id = supabase_settings.require_owner_user_id()
        client = build_supabase_client(supabase_settings, server=True)
        ledger = SupabaseCostLedger(client, owner_user_id)
    else:
        ledger = CostLedger()

    return CostScaleControl(
        pricing=pricing,
        ledger=ledger,
        limits=limits,
        fail_closed_on_missing_pricing=True,
    )


def parse_pricing_catalog(raw: str | None) -> dict[tuple[str, str], ProviderPricing]:
    """Parse reviewed runtime pricing without hard-coding volatile vendor prices.

    Expected JSON shape:
    {
      "openai": {
        "model-name": {"input": "1.00", "cached_input": "0.10", "output": "4.00"},
        "*": {"input": "1.00", "output": "4.00"}
      }
    }
    """

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
        for model, rates in models.items():
            if not isinstance(model, str) or not model.strip() or not isinstance(rates, dict):
                raise RuntimeError("AI_PRICING_JSON model entries are invalid")
            result[(provider.strip(), model.strip())] = _parse_rates(rates)
    return result


def _parse_rates(rates: dict[str, Any]) -> ProviderPricing:
    try:
        input_rate = Decimal(str(rates["input"]))
        output_rate = Decimal(str(rates["output"]))
        cached_raw = rates.get("cached_input")
        cached_rate = Decimal(str(cached_raw)) if cached_raw is not None else None
    except (KeyError, InvalidOperation, ValueError) as exc:
        raise RuntimeError("AI_PRICING_JSON rates must be numeric input/output values") from exc
    return ProviderPricing(
        input_per_million=input_rate,
        cached_input_per_million=cached_rate,
        output_per_million=output_rate,
    )
