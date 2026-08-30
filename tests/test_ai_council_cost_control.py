from decimal import Decimal

import pytest

from jafar.ai_council import AICouncil
from jafar.cost_scale_control import CostScaleControl, ProviderPricing, UsageContext
from jafar.model_router import ModelRequest, ModelResponse


class FakeProvider:
    def __init__(self, key: str) -> None:
        self.key = key
        self.calls = 0

    def available(self) -> bool:
        return True

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        return ModelResponse(
            provider=self.key,
            model="test-model",
            text=self.key,
            metadata={"usage": {"input_tokens": 100, "output_tokens": 20}},
        )


def make_control() -> CostScaleControl:
    pricing = ProviderPricing(
        input_per_million=Decimal(1),
        output_per_million=Decimal(2),
    )
    return CostScaleControl(
        pricing={
            ("openai", "test-model"): pricing,
            ("qwen", "test-model"): pricing,
        }
    )


def request(**overrides) -> ModelRequest:
    values = {
        "prompt": "analyze",
        "task": "legal_analysis",
        "confidential": False,
        "allowed_providers": ("openai", "qwen"),
        "usage_context": UsageContext(
            request_id="council-1",
            user_id="user-1",
            operation="ai_council",
            matter_id="matter-1",
        ),
        "estimated_cost_usd": Decimal("0.01"),
    }
    values.update(overrides)
    return ModelRequest(**values)


def test_council_meters_each_provider_independently() -> None:
    providers = {"openai": FakeProvider("openai"), "qwen": FakeProvider("qwen")}
    control = make_control()

    result = AICouncil(providers, cost_control=control).run(request())

    assert result.providers == ("openai", "qwen")
    records = control.ledger.records()
    assert len(records) == 2
    assert {item.context.request_id for item in records} == {
        "council-1:council:openai",
        "council-1:council:qwen",
    }


def test_council_kill_switch_prevents_provider_call() -> None:
    openai = FakeProvider("openai")
    qwen = FakeProvider("qwen")
    control = make_control()
    control.disable_provider("qwen")

    result = AICouncil(
        {"openai": openai, "qwen": qwen},
        cost_control=control,
    ).run(request(), minimum_responses=1)

    assert result.providers == ("openai",)
    assert qwen.calls == 0


def test_council_fails_closed_without_attribution_or_estimate() -> None:
    providers = {"openai": FakeProvider("openai"), "qwen": FakeProvider("qwen")}
    council = AICouncil(providers, cost_control=make_control())

    with pytest.raises(RuntimeError, match="usage_context_required"):
        council.run(
            ModelRequest(
                prompt="analyze",
                task="legal_analysis",
                confidential=False,
                allowed_providers=("openai", "qwen"),
                estimated_cost_usd=Decimal("0.01"),
            )
        )

    with pytest.raises(RuntimeError, match="cost_estimate_required"):
        council.run(
            ModelRequest(
                prompt="analyze",
                task="legal_analysis",
                confidential=False,
                allowed_providers=("openai", "qwen"),
                usage_context=UsageContext(
                    request_id="council-2",
                    user_id="user-1",
                    operation="ai_council",
                ),
            )
        )
