from decimal import Decimal

import pytest

from jafar import main


def _secure_production(monkeypatch) -> None:
    monkeypatch.setattr(main.settings, "environment", "production")
    monkeypatch.setattr(main.settings, "api_key", "a-secure-production-api-key-123456")
    monkeypatch.setattr(main.settings, "lawyer_approver_id", "lawyer-1")
    monkeypatch.setattr(main, "validate_storage_security", lambda _settings: None)
    monkeypatch.setattr(main.settings, "storage_backend", "supabase")
    monkeypatch.setattr(main.settings, "ai_cost_control_enabled", True)
    monkeypatch.setattr(
        main.settings,
        "ai_pricing_json",
        '{"openai":{"*":{"input":"1","output":"4"}}}',
    )
    monkeypatch.setattr(main.settings, "ai_pricing_version", "2026-08-28-reviewed")
    monkeypatch.setattr(main.settings, "ai_cost_per_request_usd", Decimal(1))
    monkeypatch.setattr(main.settings, "ai_cost_user_daily_usd", Decimal(10))
    monkeypatch.setattr(main.settings, "ai_cost_user_monthly_usd", Decimal(100))
    monkeypatch.setattr(main.settings, "ai_cost_matter_daily_usd", Decimal(20))
    monkeypatch.setattr(main.settings, "ai_cost_matter_monthly_usd", Decimal(200))
    monkeypatch.setattr(main.settings, "ai_cost_global_daily_usd", Decimal(1000))
    monkeypatch.setattr(main.settings, "ai_queue_backend", "supabase")
    monkeypatch.setattr(main.settings, "ai_queue_worker_claim_limit", 5)


def test_secure_production_scale_configuration_is_accepted(monkeypatch) -> None:
    _secure_production(monkeypatch)
    main.validate_runtime_security()


def test_production_requires_cost_control(monkeypatch) -> None:
    _secure_production(monkeypatch)
    monkeypatch.setattr(main.settings, "ai_cost_control_enabled", False)

    with pytest.raises(RuntimeError, match="requires AI cost control"):
        main.validate_runtime_security()


def test_production_requires_versioned_reviewed_pricing(monkeypatch) -> None:
    _secure_production(monkeypatch)
    monkeypatch.setattr(main.settings, "ai_pricing_version", None)

    with pytest.raises(RuntimeError, match="AI_PRICING_VERSION"):
        main.validate_runtime_security()


def test_production_requires_all_positive_spend_limits(monkeypatch) -> None:
    _secure_production(monkeypatch)
    monkeypatch.setattr(main.settings, "ai_cost_user_daily_usd", Decimal(0))

    with pytest.raises(RuntimeError, match="AI_COST_USER_DAILY_USD"):
        main.validate_runtime_security()


def test_production_requires_durable_distributed_queue(monkeypatch) -> None:
    _secure_production(monkeypatch)
    monkeypatch.setattr(main.settings, "ai_queue_backend", "memory")

    with pytest.raises(RuntimeError, match="durable Supabase AI queue"):
        main.validate_runtime_security()


def test_production_rejects_unbounded_worker_claim_limit(monkeypatch) -> None:
    _secure_production(monkeypatch)
    monkeypatch.setattr(main.settings, "ai_queue_worker_claim_limit", 1000)

    with pytest.raises(RuntimeError, match="must be between 1 and 50"):
        main.validate_runtime_security()
