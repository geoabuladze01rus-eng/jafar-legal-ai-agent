from datetime import UTC, datetime
from decimal import Decimal

import pytest

from jafar.cost_scale_control import (
    BudgetLimits,
    CostLedger,
    CostRecord,
    CostScaleControl,
    ProviderPricing,
    TokenUsage,
    UsageContext,
    calculate_cost,
)


def context(request_id: str = "r1", user_id: str = "u1") -> UsageContext:
    return UsageContext(
        request_id=request_id,
        user_id=user_id,
        operation="legal_analysis",
        matter_id="m1",
    )


def test_usage_normalizes_openai_and_chat_completion_shapes() -> None:
    openai = TokenUsage.from_provider_metadata(
        {
            "usage": {
                "input_tokens": 1000,
                "output_tokens": 200,
                "input_tokens_details": {"cached_tokens": 600},
            }
        }
    )
    chat = TokenUsage.from_provider_metadata(
        {
            "usage": {
                "prompt_tokens": 500,
                "completion_tokens": 100,
                "prompt_tokens_details": {"cached_tokens": 50},
            }
        }
    )

    assert openai == TokenUsage(input_tokens=1000, cached_input_tokens=600, output_tokens=200)
    assert chat == TokenUsage(input_tokens=500, cached_input_tokens=50, output_tokens=100)


def test_cost_uses_cached_rate_only_for_cached_input() -> None:
    pricing = ProviderPricing(
        input_per_million=Decimal(10),
        cached_input_per_million=Decimal(1),
        output_per_million=Decimal(20),
    )
    usage = TokenUsage(input_tokens=1_000_000, cached_input_tokens=400_000, output_tokens=100_000)

    assert calculate_cost(usage, pricing) == Decimal("8.40000000")


def test_cost_ledger_rejects_duplicate_request_accounting() -> None:
    ledger = CostLedger()
    record = CostRecord(
        context=context(),
        provider="openai",
        model="test-model",
        usage=TokenUsage(input_tokens=100),
        cost_usd=Decimal("0.01"),
    )
    ledger.record(record)

    with pytest.raises(ValueError, match="duplicate_cost_request_id"):
        ledger.record(record)


def test_preflight_enforces_user_and_global_budgets() -> None:
    ledger = CostLedger()
    now = datetime.now(UTC)
    ledger.record(
        CostRecord(
            context=context("existing"),
            provider="openai",
            model="test-model",
            usage=TokenUsage(input_tokens=100),
            cost_usd=Decimal("0.80"),
            recorded_at=now,
        )
    )
    control = CostScaleControl(
        pricing={},
        ledger=ledger,
        limits=BudgetLimits(
            per_request_usd=Decimal("0.50"),
            per_user_daily_usd=Decimal("1.00"),
            global_daily_usd=Decimal("1.10"),
        ),
    )

    with pytest.raises(RuntimeError, match="per_request"):
        control.preflight(context("too-large"), estimated_cost_usd=Decimal("0.60"))
    with pytest.raises(RuntimeError, match="user_daily"):
        control.preflight(context("user-budget"), estimated_cost_usd=Decimal("0.30"))
    with pytest.raises(RuntimeError, match="global_daily"):
        control.preflight(
            context("global-budget", user_id="another-user"),
            estimated_cost_usd=Decimal("0.31"),
        )


def test_meter_response_records_tokens_and_cost_without_raw_output() -> None:
    control = CostScaleControl(
        pricing={
            ("openai", "model-a"): ProviderPricing(
                input_per_million=Decimal(2),
                cached_input_per_million=Decimal("0.2"),
                output_per_million=Decimal(8),
            )
        }
    )

    record = control.meter_response(
        context=context(),
        provider="openai",
        model="model-a",
        metadata={
            "usage": {
                "input_tokens": 1000,
                "output_tokens": 200,
                "input_tokens_details": {"cached_tokens": 500},
            },
            "raw_response": "must never be copied into the ledger",
        },
    )

    assert record is not None
    assert record.usage == TokenUsage(input_tokens=1000, cached_input_tokens=500, output_tokens=200)
    assert record.cost_usd == Decimal("0.00270000")
    assert not hasattr(record, "metadata")


def test_metering_fails_closed_when_usage_or_pricing_is_missing() -> None:
    control = CostScaleControl(pricing={})

    with pytest.raises(RuntimeError, match="usage_metadata_missing"):
        control.meter_response(
            context=context("missing-usage"),
            provider="openai",
            model="model-a",
            metadata={},
        )

    with pytest.raises(RuntimeError, match="pricing_missing"):
        control.meter_response(
            context=context("missing-price"),
            provider="openai",
            model="model-a",
            metadata={"usage": {"input_tokens": 1, "output_tokens": 1}},
        )


def test_provider_kill_switch_is_fail_closed() -> None:
    control = CostScaleControl(pricing={})

    assert control.provider_enabled("openai") is True
    control.disable_provider("OpenAI")
    assert control.provider_enabled("openai") is False
    control.enable_provider("openai")
    assert control.provider_enabled("openai") is True
