from decimal import Decimal

import pytest

from jafar.cost_scale_control import CostScaleControl, ProviderPricing, UsageContext
from jafar.model_router import ModelControlError, ModelRequest, ModelResponse, ModelRouter


class FakeProvider:
    def __init__(self, key: str, *, model: str = "model-a", available: bool = True) -> None:
        self.key = key
        self.model = model
        self._available = available
        self.calls = 0

    def available(self) -> bool:
        return self._available

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        return ModelResponse(
            provider=self.key,
            model=self.model,
            text=f"response:{self.key}",
            metadata={
                "usage": {
                    "input_tokens": 1000,
                    "output_tokens": 100,
                    "input_tokens_details": {"cached_tokens": 500},
                }
            },
        )


def control() -> CostScaleControl:
    rate = ProviderPricing(
        input_per_million=Decimal(2),
        cached_input_per_million=Decimal("0.2"),
        output_per_million=Decimal(8),
    )
    return CostScaleControl(
        pricing={
            ("openai", "*"): rate,
            ("deepseek", "*"): rate,
        }
    )


def metered_request(**overrides) -> ModelRequest:
    values = {
        "prompt": "analyze",
        "task": "technical_analysis",
        "confidential": False,
        "usage_context": UsageContext(
            request_id="req-1",
            user_id="user-1",
            operation="technical_analysis",
            matter_id="matter-1",
        ),
        "estimated_cost_usd": Decimal("0.01"),
    }
    values.update(overrides)
    return ModelRequest(**values)


def test_router_records_actual_provider_usage() -> None:
    deepseek = FakeProvider("deepseek")
    openai = FakeProvider("openai")
    scale = control()
    router = ModelRouter({"deepseek": deepseek, "openai": openai}, cost_control=scale)

    responses = router.run(metered_request())

    assert responses[0].provider == "deepseek"
    assert deepseek.calls == 1
    records = scale.ledger.records()
    assert len(records) == 1
    assert records[0].provider == "deepseek"
    assert records[0].context.user_id == "user-1"
    assert records[0].context.matter_id == "matter-1"
    assert records[0].context.request_id == "req-1:primary:deepseek"
    assert records[0].cost_usd > 0


def test_kill_switch_removes_provider_before_dispatch() -> None:
    deepseek = FakeProvider("deepseek")
    openai = FakeProvider("openai")
    scale = control()
    scale.disable_provider("deepseek")
    router = ModelRouter({"deepseek": deepseek, "openai": openai}, cost_control=scale)

    with pytest.raises(ModelControlError, match="disabled"):
        router.run(metered_request())
    assert deepseek.calls == 0
    assert openai.calls == 0


def test_cost_control_rejects_unattributed_or_unestimated_requests() -> None:
    provider = FakeProvider("deepseek")
    router = ModelRouter({"deepseek": provider}, cost_control=control())

    with pytest.raises(ModelControlError, match="usage_context_required"):
        router.run(
            ModelRequest(
                prompt="analyze",
                task="technical_analysis",
                confidential=False,
                estimated_cost_usd=Decimal("0.01"),
            )
        )
    with pytest.raises(ModelControlError, match="cost_estimate_required"):
        router.run(
            ModelRequest(
                prompt="analyze",
                task="technical_analysis",
                confidential=False,
                usage_context=UsageContext(
                    request_id="req-2",
                    user_id="user-1",
                    operation="technical_analysis",
                ),
            )
        )
    assert provider.calls == 0


def test_verifier_is_metered_as_independent_call() -> None:
    deepseek = FakeProvider("deepseek")
    openai = FakeProvider("openai")
    scale = control()
    router = ModelRouter({"deepseek": deepseek, "openai": openai}, cost_control=scale)

    responses = router.run(metered_request(verification=True))

    assert [item.provider for item in responses] == ["deepseek", "openai"]
    request_ids = {item.context.request_id for item in scale.ledger.records()}
    assert request_ids == {
        "req-1:primary:deepseek",
        "req-1:verifier:openai",
    }
