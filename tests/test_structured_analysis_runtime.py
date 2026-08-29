from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from jafar.cost_scale_control import (
    BudgetLimits,
    CostLedger,
    CostScaleControl,
    ProviderPricing,
)
from jafar.domains import DocumentTask, MatterType
from jafar.legal_models import AnalysisRequest, LegalAnalysis
from jafar.structured_analysis_runtime import MeteredStructuredLegalAnalyzer


@dataclass
class _Config:
    model: str = "model-a"
    max_output_tokens: int = 1000


class _Analyzer:
    key = "openai"
    config = _Config()

    def __init__(self, *, fail: bool = False, value_fail: bool = False) -> None:
        self.fail = fail
        self.value_fail = value_fail
        self.calls = 0

    def analyze_with_usage(self, *, text, task, matter_type):
        self.calls += 1
        if self.value_fail:
            raise ValueError("structured response invalid after dispatch")
        if self.fail:
            raise RuntimeError("provider failed after dispatch")
        return (
            LegalAnalysis(
                task=task,
                matter_type=matter_type,
                summary="Проверенный структурированный анализ",
            ),
            {"usage": {"input_tokens": 500, "output_tokens": 100}},
        )


class _Reservation:
    def __init__(self, reservation_id):
        self.reservation_id = reservation_id


class _Reservations:
    def __init__(self):
        self.reserved = []
        self.settled = []
        self.released = []

    def reserve(self, *, context, estimated_cost_usd, limits, ttl_seconds=300):
        self.reserved.append((context, estimated_cost_usd, limits))
        return _Reservation(context.request_id)

    def settle(self, reservation_id):
        self.settled.append(reservation_id)

    def release(self, reservation_id):
        self.released.append(reservation_id)


def _request(text: str = "Материалы уголовного дела и процессуальная позиция защиты.") -> AnalysisRequest:
    return AnalysisRequest(
        text=text,
        task=DocumentTask.LEGAL_ANALYSIS,
        matter_type=MatterType.CRIMINAL,
        matter_id="matter-1",
    )


def _control() -> CostScaleControl:
    return CostScaleControl(
        pricing={
            ("openai", "model-a"): ProviderPricing(
                input_per_million=Decimal("1"),
                output_per_million=Decimal("4"),
            )
        },
        ledger=CostLedger(),
        limits=BudgetLimits(per_request_usd=Decimal("1")),
        pricing_version="2026-08-28-reviewed",
    )


def test_structured_analysis_preflights_reserves_meters_and_settles() -> None:
    analyzer = _Analyzer()
    reservations = _Reservations()
    control = _control()
    runtime = MeteredStructuredLegalAnalyzer(
        analyzer=analyzer,  # type: ignore[arg-type]
        cost_control=control,
        user_id="lawyer-1",
        reservations=reservations,  # type: ignore[arg-type]
    )

    analysis = runtime.analyze(_request())

    assert analysis.summary == "Проверенный структурированный анализ"
    assert analyzer.calls == 1
    assert len(reservations.reserved) == 1
    assert len(reservations.settled) == 1
    assert reservations.released == []
    records = control.ledger.records()  # type: ignore[attr-defined]
    assert len(records) == 1
    assert records[0].context.matter_id == "matter-1"
    assert records[0].pricing_version == "2026-08-28-reviewed"


def test_unknown_provider_failure_keeps_reservation_held_for_ttl() -> None:
    analyzer = _Analyzer(fail=True)
    reservations = _Reservations()
    runtime = MeteredStructuredLegalAnalyzer(
        analyzer=analyzer,  # type: ignore[arg-type]
        cost_control=_control(),
        user_id="lawyer-1",
        reservations=reservations,  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="provider failed"):
        runtime.analyze(_request())

    assert len(reservations.reserved) == 1
    assert reservations.settled == []
    assert reservations.released == []


def test_post_dispatch_value_error_keeps_reservation_held() -> None:
    analyzer = _Analyzer(value_fail=True)
    reservations = _Reservations()
    runtime = MeteredStructuredLegalAnalyzer(
        analyzer=analyzer,  # type: ignore[arg-type]
        cost_control=_control(),
        user_id="lawyer-1",
        reservations=reservations,  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="structured response invalid"):
        runtime.analyze(_request())

    assert analyzer.calls == 1
    assert len(reservations.reserved) == 1
    assert reservations.settled == []
    assert reservations.released == []


def test_empty_input_is_rejected_before_spend_reservation() -> None:
    analyzer = _Analyzer()
    reservations = _Reservations()
    runtime = MeteredStructuredLegalAnalyzer(
        analyzer=analyzer,  # type: ignore[arg-type]
        cost_control=_control(),
        user_id="lawyer-1",
        reservations=reservations,  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="document text must not be empty"):
        runtime.analyze(_request("   "))

    assert analyzer.calls == 0
    assert reservations.reserved == []
    assert reservations.settled == []
    assert reservations.released == []


def test_disabled_provider_blocks_before_dispatch() -> None:
    analyzer = _Analyzer()
    control = _control()
    control.disable_provider("openai")
    runtime = MeteredStructuredLegalAnalyzer(
        analyzer=analyzer,  # type: ignore[arg-type]
        cost_control=control,
        user_id="lawyer-1",
    )

    with pytest.raises(RuntimeError, match="provider_disabled"):
        runtime.analyze(_request())
    assert analyzer.calls == 0
