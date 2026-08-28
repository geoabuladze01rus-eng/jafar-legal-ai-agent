from decimal import Decimal

import pytest

from jafar.config import Settings
from jafar.cost_runtime import build_cost_scale_control, parse_pricing_catalog
from jafar.cost_scale_control import CostLedger


def settings(**values) -> Settings:
    return Settings(_env_file=None, **values)


def test_pricing_catalog_is_configuration_driven() -> None:
    catalog = parse_pricing_catalog(
        '{"openai":{"model-a":{"input":"2.5","cached_input":"0.25","output":"10"}}}'
    )

    price = catalog[("openai", "model-a")]
    assert price.input_per_million == Decimal("2.5")
    assert price.cached_input_per_million == Decimal("0.25")
    assert price.output_per_million == Decimal("10")


def test_pricing_catalog_rejects_missing_or_invalid_configuration() -> None:
    with pytest.raises(RuntimeError, match="AI_PRICING_JSON is required"):
        parse_pricing_catalog(None)
    with pytest.raises(RuntimeError, match="valid JSON"):
        parse_pricing_catalog("not-json")
    with pytest.raises(RuntimeError, match="numeric input/output"):
        parse_pricing_catalog('{"openai":{"*":{"input":"x","output":"1"}}}')


def test_cost_runtime_is_opt_in_for_local_development() -> None:
    assert build_cost_scale_control(settings(ai_cost_control_enabled=False)) is None


def test_development_cost_runtime_uses_in_memory_ledger_and_limits() -> None:
    control = build_cost_scale_control(
        settings(
            ai_cost_control_enabled=True,
            ai_pricing_json='{"openai":{"*":{"input":"1","output":"4"}}}',
            ai_cost_per_request_usd=Decimal("0.25"),
            ai_cost_user_daily_usd=Decimal("2.00"),
        )
    )

    assert control is not None
    assert isinstance(control.ledger, CostLedger)
    assert control.limits.per_request_usd == Decimal("0.25")
    assert control.limits.per_user_daily_usd == Decimal("2.00")


def test_production_cost_runtime_requires_persistent_storage() -> None:
    with pytest.raises(RuntimeError, match="persistent Supabase storage"):
        build_cost_scale_control(
            settings(
                environment="production",
                storage_backend="memory",
                ai_cost_control_enabled=True,
                ai_pricing_json='{"openai":{"*":{"input":"1","output":"4"}}}',
            )
        )
