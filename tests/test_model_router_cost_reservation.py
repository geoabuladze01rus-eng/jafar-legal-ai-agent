from datetime import UTC, datetime
from decimal import Decimal

import pytest

from jafar.cost_scale_control import BudgetLimits, CostScaleControl, ProviderPricing, UsageContext
from jafar.model_router import (
    ModelRequest,
    ModelResponse,
    ModelRouter,
    ProviderDispatchUncertainError,
)
from jafar.supabase_cost_reservations import CostReservation


class FakeProvider:
    key = "openai"

    def __init__(self, *, fail: bool = False, usage: bool = True) -> None:
        self.fail = fail
        self.usage = usage
        self.calls = 0

    def available(self) -> bool:
        return True

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        if self.fail:
            raise TimeoutError("provider down")
        metadata = {"usage": {"input_tokens": 100, "output_tokens": 20}} if self.usage else {}
        return ModelResponse("openai", "test", "ok", metadata)


class FakeReservations:
    def __init__(self) -> None:
        self.reserved = []
        self.released = []
        self.settled = []

    def reserve(self, *, context, estimated_cost_usd, limits, ttl_seconds=300):
        self.reserved.append((context.request_id, estimated_cost_usd, limits))
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


def make_router(provider: FakeProvider, reservations: FakeReservations) -> ModelRouter:
    control = CostScaleControl(
        pricing={
            ("openai", "test"): ProviderPricing(
                input_per_million=Decimal(1),
                output_per_million=Decimal(2),
            )
        },
        limits=BudgetLimits(per_request_usd=Decimal(1)),
    )
    return ModelRouter(
        {"openai": provider},
        cost_control=control,
        cost_reservations=reservations,
    )


def request() -> ModelRequest:
    return ModelRequest(
        prompt="analyze",
        task="legal_analysis",
        confidential=True,
        allowed_providers=("openai",),
        usage_context=UsageContext("req-1", "user-1", "legal-analysis", "matter-1"),
        estimated_cost_usd=Decimal("0.10"),
    )


def test_router_reserves_before_dispatch_and_settles_after_metering() -> None:
    provider = FakeProvider()
    reservations = FakeReservations()
    result = make_router(provider, reservations).run(request())

    assert result[0].text == "ok"
    assert reservations.reserved[0][0] == "req-1:primary:openai"
    assert reservations.released == []
    assert reservations.settled == ["req-1:primary:openai"]


def test_provider_failure_keeps_reservation_held_and_blocks_automatic_replay() -> None:
    provider = FakeProvider(fail=True)
    reservations = FakeReservations()

    with pytest.raises(ProviderDispatchUncertainError, match="dispatch outcome is uncertain"):
        make_router(provider, reservations).run(request())

    assert provider.calls == 1
    assert reservations.released == []
    assert reservations.settled == []


def test_accounting_failure_keeps_reservation_held_after_provider_was_called() -> None:
    provider = FakeProvider(usage=False)
    reservations = FakeReservations()

    with pytest.raises(ProviderDispatchUncertainError, match="accounting outcome is uncertain"):
        make_router(provider, reservations).run(request())

    assert provider.calls == 1
    assert reservations.released == []
    assert reservations.settled == []
