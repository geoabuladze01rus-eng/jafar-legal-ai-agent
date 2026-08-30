import pytest

from jafar.scale_telemetry import ScaleTelemetry


def test_scale_telemetry_exposes_only_aggregate_operational_metrics() -> None:
    telemetry = ScaleTelemetry()
    telemetry.increment("cache_hit", 3)
    telemetry.increment("rate_limit_rejected")

    snapshot = telemetry.snapshot(
        queue_depth=7,
        executing_actions=2,
        reconciliation_candidates=1,
        disabled_providers=("Gemini", " deepseek ", "Gemini"),
    )

    assert snapshot.queue_depth == 7
    assert snapshot.executing_actions == 2
    assert snapshot.reconciliation_candidates == 1
    assert snapshot.disabled_providers == ("deepseek", "gemini")
    assert snapshot.counters["cache_hit"] == 3
    assert snapshot.counters["rate_limit_rejected"] == 1
    assert "user_id" not in snapshot.counters
    assert "matter_id" not in snapshot.counters


def test_arbitrary_high_cardinality_or_sensitive_dimensions_are_rejected() -> None:
    telemetry = ScaleTelemetry()

    for unsafe in (
        "user:arthur",
        "matter:criminal-case-1",
        "prompt:secret",
        "client@example.com",
    ):
        with pytest.raises(ValueError, match="unsupported_scale_telemetry_event"):
            telemetry.increment(unsafe)


def test_invalid_gauges_and_increment_values_fail_closed() -> None:
    telemetry = ScaleTelemetry()

    with pytest.raises(ValueError, match="telemetry_increment_must_be_positive"):
        telemetry.increment("cache_hit", 0)

    with pytest.raises(ValueError, match="telemetry_gauges_must_be_non_negative"):
        telemetry.snapshot(
            queue_depth=-1,
            executing_actions=0,
            reconciliation_candidates=0,
        )
