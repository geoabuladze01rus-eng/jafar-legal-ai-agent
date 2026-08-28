from decimal import Decimal

import pytest

from jafar.config import Settings
from jafar.cost_runtime import (
    build_cost_scale_control,
    parse_pricing_catalog,
    validate_production_ai_scale,
)
from jafar.cost_scale_control import CostLedger


def settings(**values) -> Settings:
    return Settings(_env_file=None, **values)


def valid_production_settings(**overrides) -> Settings:
    values = {
        "environment": "production",
        "storage_backend": "supabase",
        "ai_cost_control_enabled": True,
        "ai_queue_backend": "supabase",
        "ai_pricing_json": '{"openai":{"*":{"input":"1","cached_input":"0.1","output":"4"}}}',
        "ai_cost_per_request_usd": Decimal("0.50"),
        "ai_cost_user_daily_usd": Decimal("5.00"),
        "ai_cost_user_monthly_usd": Decimal("100.00"),
        "ai_cost_global_daily_usd": Decimal("500.00"),
        "ai_queue_worker_claim_limit": 5,
    }
    values.update(overrides)
    return settings(**values)


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
    with pytest.raises(RuntimeError, match="finite non-negative"):
        parse_pricing_catalog('{"openai":{"*":{"input":"-1","output":"1"}}}')
    with pytest.raises(RuntimeError, match="finite non-negative"):
        parse_pricing_catalog('{"openai":{"*":{"input":"NaN","output":"1"}}}')


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
            valid_production_settings(storage_backend="memory")
        )


def test_production_requires_cost_control_and_durable_queue() -> None:
    with pytest.raises(RuntimeError, match="requires AI cost control"):
        validate_production_ai_scale(
            valid_production_settings(ai_cost_control_enabled=False)
        )
    with pytest.raises(RuntimeError, match="durable Supabase AI queue"):
        validate_production_ai_scale(
            valid_production_settings(ai_queue_backend="memory")
        )


def test_production_requires_every_positive_spend_ceiling() -> None:
    with pytest.raises(RuntimeError, match="AI_COST_GLOBAL_DAILY_USD"):
        validate_production_ai_scale(
            valid_production_settings(ai_cost_global_daily_usd=None)
        )
    with pytest.raises(RuntimeError, match="AI_COST_PER_REQUEST_USD"):
        validate_production_ai_scale(
            valid_production_settings(ai_cost_per_request_usd=Decimal("0"))
        )


def test_production_rejects_incoherent_spend_hierarchy() -> None:
    with pytest.raises(RuntimeError, match="Per-request AI ceiling"):
        validate_production_ai_scale(
            valid_production_settings(
                ai_cost_per_request_usd=Decimal("10"),
                ai_cost_user_daily_usd=Decimal("5"),
            )
        )
    with pytest.raises(RuntimeError, match="monthly ceiling"):
        validate_production_ai_scale(
            valid_production_settings(
                ai_cost_user_daily_usd=Decimal("5"),
                ai_cost_user_monthly_usd=Decimal("4"),
            )
        )
    with pytest.raises(RuntimeError, match="global daily ceiling"):
        validate_production_ai_scale(
            valid_production_settings(
                ai_cost_user_daily_usd=Decimal("5"),
                ai_cost_global_daily_usd=Decimal("4"),
            )
        )


def test_production_rejects_invalid_worker_claim_limit() -> None:
    with pytest.raises(RuntimeError, match="between 1 and 50"):
        validate_production_ai_scale(
            valid_production_settings(ai_queue_worker_claim_limit=51)
        )
