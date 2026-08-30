from datetime import UTC, datetime
from decimal import Decimal

import pytest

from jafar.ai_council import AICouncil
from jafar.cost_scale_control import BudgetLimits, CostScaleControl, ProviderPricing, UsageContext
from jafar.model_router import ModelRequest, ModelResponse
from jafar.supabase_cost_reservations import CostReservation


class FakeProvider:
    def __init__(self, key: str, *, fail: bool = False, usage: bool = True) -> None:
        self.key = key
        self.fail = fail
        self.usage = usage
        self.calls = 0

    def available(self) -> bool:
        return True

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        if self.fail:
            raise TimeoutError("provider unavailable")
        metadata = {"usage": {"input_tokens": 100, "output_tokens": 20}} if self.usage else {}
        return ModelResponse(self.key, "test", self.key, metadata)


class FakeReservations:
    def __init__(self) -> None:
        self.reserved = []
        self.released = []
        self.settled = []

    def reserve(self, *, context, estimated_cost_usd, limits, ttl_seconds=300):
        self.reserved.append(context.request_id)
        return CostReservation(
            reservation_id=context.request_id,
            context=context,
            estimated_cost_usd=estimated_cost_usd,
            expires_at=datetime.now(UTC),
        )

    def release(self, reservation_id: str) -> None:
        self.released.append(reservation_id)

    def settle(self, reservation_id: str) -> None:
        self.settled.append(reservation_id)


def make_control() -> CostScaleControl:
    price = ProviderPricing(
        input_per_million=Decimal(1),
        output_per_million=Decimal(2),
    )
    return CostScaleControl(
        pricing={(provider, "test"): price for provider in ("openai", "qwen")},
        limits=BudgetLimits(per_request_usd=Decimal(1)),
    )


def request() -> ModelRequest:
    return ModelRequest(
        prompt="analyze",
        task="legal_analysis",
        confidential=False,
        allowed_providers=("openai", "qwen"),
        usage_context=UsageContext("req-council", "user-1", "ai-council", "matter-1"),
        estimated_cost_usd=Decimal("0.10"),
    )


def test_council_reserves_each_provider_before_dispatch_and_settles() -> None:
    reservations = FakeReservations()
    council = AICouncil(
        {"openai": FakeProvider("openai"), "qwen": FakeProvider("qwen")},
        cost_control=make_control(),
        cost_reservations=reservations,
    )

    result = council.run(request())

    assert result.providers == ("openai", "qwen")
    assert result.uncertain_providers == ()
    assert reservations.reserved == [
        "req-council:council:openai",
        "req-council:council:qwen",
    ]
    assert reservations.released == []
    assert reservations.settled == reservations.reserved


def test_council_provider_failure_keeps_uncertain_reservation_held() -> None:
    reservations = FakeReservations()
    council = AICouncil(
        {"openai": FakeProvider("openai"), "qwen": FakeProvider("qwen", fail=True)},
        cost_control=make_control(),
        cost_reservations=reservations,
    )

    result = council.run(request(), minimum_responses=1)

    assert result.providers == ("openai",)
    assert result.failed_providers == ("qwen",)
    assert result.uncertain_providers == ("qwen",)
    assert reservations.settled == ["req-council:council:openai"]
    assert reservations.released == []


def test_council_accounting_failure_keeps_reservation_active_for_reconciliation() -> None:
    reservations = FakeReservations()
    openai = FakeProvider("openai", usage=False)
    qwen = FakeProvider("qwen", usage=False)
    council = AICouncil(
        {"openai": openai, "qwen": qwen},
        cost_control=make_control(),
        cost_reservations=reservations,
    )

    with pytest.raises(RuntimeError, match="requires at least"):
        council.run(request())

    assert openai.calls == 1
    assert qwen.calls == 1
    assert reservations.released == []
    assert reservations.settled == []
