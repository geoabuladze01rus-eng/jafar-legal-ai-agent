from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from jafar.cost_scale_control import BudgetLimits, CostScaleControl, UsageContext
from jafar.model_router import (
    ModelControlError,
    ModelRequest,
    ModelResponse,
    ModelRouter,
    ProviderDispatchUncertainError,
)
from jafar.supabase_cost_reservations import CostReservation


class _Provider:
    def __init__(self, key: str, *, available: bool = True, error: Exception | None = None):
        self.key = key
        self._available = available
        self.error = error
        self.calls = 0

    def available(self) -> bool:
        return self._available

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return ModelResponse(
            provider=self.key,
            model=f"{self.key}-model",
            text="ok",
            metadata={"usage": {"input_tokens": 1, "output_tokens": 1}},
        )


class _FailingReservations:
    def __init__(self) -> None:
        self.calls = 0

    def reserve(self, **_kwargs):
        self.calls += 1
        raise RuntimeError("reservation backend unavailable")

    def release(self, _reservation_id: str) -> None:
        raise AssertionError("pre-dispatch reservation failure must not release a nonexistent claim")

    def settle(self, _reservation_id: str) -> None:
        raise AssertionError("failed reservation must never settle")


class _Reservations:
    def __init__(self) -> None:
        self.settled: list[str] = []

    def reserve(self, *, context, estimated_cost_usd, limits, ttl_seconds=300):
        return CostReservation(
            reservation_id=context.request_id,
            context=context,
            estimated_cost_usd=estimated_cost_usd,
            expires_at=datetime.now(timezone.utc),
        )

    def release(self, _reservation_id: str) -> None:
        pass

    def settle(self, reservation_id: str) -> None:
        self.settled.append(reservation_id)


def _context() -> UsageContext:
    return UsageContext(
        request_id="request-1",
        user_id="user-1",
        operation="legal_analysis",
        matter_id="matter-1",
    )


def _request(**changes) -> ModelRequest:
    values = {
        "prompt": "confidential facts",
        "task": "legal_analysis",
        "confidential": False,
        "allowed_providers": ("openai", "deepseek"),
        "usage_context": _context(),
        "estimated_cost_usd": Decimal("0.10"),
    }
    values.update(changes)
    return ModelRequest(**values)


def _control(**limits) -> CostScaleControl:
    return CostScaleControl(
        pricing={},
        limits=BudgetLimits(**limits),
    )


def test_budget_block_never_falls_back_to_another_provider() -> None:
    openai = _Provider("openai")
    deepseek = _Provider("deepseek")
    router = ModelRouter(
        {"openai": openai, "deepseek": deepseek},
        cost_control=_control(per_request_usd=Decimal("0.05")),
    )

    with pytest.raises(ModelControlError, match="model_cost_control_blocked"):
        router.run(_request())

    assert openai.calls == 0
    assert deepseek.calls == 0


def test_provider_kill_switch_does_not_silently_change_provider() -> None:
    openai = _Provider("openai")
    deepseek = _Provider("deepseek")
    control = _control()
    control.disable_provider("openai")
    router = ModelRouter({"openai": openai, "deepseek": deepseek}, cost_control=control)

    with pytest.raises(ModelControlError, match="disabled by scale control"):
        router.run(_request())

    assert openai.calls == 0
    assert deepseek.calls == 0


def test_missing_usage_context_and_estimate_are_non_fallback_control_errors() -> None:
    for request in (
        _request(usage_context=None),
        _request(estimated_cost_usd=None),
    ):
        openai = _Provider("openai")
        deepseek = _Provider("deepseek")
        router = ModelRouter(
            {"openai": openai, "deepseek": deepseek},
            cost_control=_control(),
        )

        with pytest.raises(ModelControlError):
            router.run(request)

        assert openai.calls == 0
        assert deepseek.calls == 0


def test_reservation_failure_never_dispatches_or_falls_back() -> None:
    openai = _Provider("openai")
    deepseek = _Provider("deepseek")
    reservations = _FailingReservations()
    router = ModelRouter(
        {"openai": openai, "deepseek": deepseek},
        cost_control=_control(),
        cost_reservations=reservations,
    )

    with pytest.raises(ModelControlError, match="model_cost_control_blocked"):
        router.run(_request())

    assert reservations.calls == 1
    assert openai.calls == 0
    assert deepseek.calls == 0


def test_unavailable_primary_can_select_an_available_permitted_provider() -> None:
    openai = _Provider("openai", available=False)
    deepseek = _Provider("deepseek")
    router = ModelRouter({"openai": openai, "deepseek": deepseek})

    responses = router.run(_request(usage_context=None, estimated_cost_usd=None))

    assert responses[0].provider == "deepseek"
    assert openai.calls == 0
    assert deepseek.calls == 1


def test_provider_dispatch_error_is_uncertain_and_never_replayed() -> None:
    openai = _Provider("openai", error=RuntimeError("transport failed"))
    deepseek = _Provider("deepseek")
    router = ModelRouter({"openai": openai, "deepseek": deepseek})

    with pytest.raises(ProviderDispatchUncertainError):
        router.run(_request(usage_context=None, estimated_cost_usd=None))

    assert openai.calls == 1
    assert deepseek.calls == 0


def test_post_dispatch_accounting_failure_never_falls_back() -> None:
    openai = _Provider("openai")
    deepseek = _Provider("deepseek")
    reservations = _Reservations()
    router = ModelRouter(
        {"openai": openai, "deepseek": deepseek},
        cost_control=_control(),
        cost_reservations=reservations,
    )

    with pytest.raises(ProviderDispatchUncertainError, match="accounting outcome is uncertain"):
        router.run(_request())

    assert openai.calls == 1
    assert deepseek.calls == 0
    assert reservations.settled == []
