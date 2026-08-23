from __future__ import annotations

import pytest

from jafar.model_router import ModelRequest, ModelResponse, ModelRouter


class Provider:
    def __init__(self, key: str, available: bool = True, fail: bool = False):
        self.key = key
        self._available = available
        self.fail = fail
        self.calls = 0

    def available(self) -> bool:
        return self._available

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        if self.fail:
            raise RuntimeError("provider failure")
        return ModelResponse(self.key, "test-model", "ok", {})


def test_confidential_request_defaults_to_openai_only() -> None:
    providers = {"openai": Provider("openai"), "deepseek": Provider("deepseek")}
    router = ModelRouter(providers)

    decision = router.decide(ModelRequest(prompt="private legal document", task="legal_analysis"))

    assert decision.primary == "openai"


def test_confidential_request_does_not_fallback_to_unlisted_provider() -> None:
    providers = {
        "openai": Provider("openai", fail=True),
        "deepseek": Provider("deepseek"),
    }
    router = ModelRouter(providers)

    with pytest.raises(RuntimeError, match="All permitted AI providers failed"):
        router.run(ModelRequest(prompt="private legal document", task="legal_analysis"))

    assert providers["openai"].calls == 1
    assert providers["deepseek"].calls == 0


def test_explicit_allowlist_can_enable_fallback() -> None:
    providers = {
        "openai": Provider("openai", fail=True),
        "deepseek": Provider("deepseek"),
    }
    router = ModelRouter(providers)

    responses = router.run(
        ModelRequest(
            prompt="non-confidential text",
            task="legal_analysis",
            confidential=False,
            allowed_providers=("openai", "deepseek"),
        )
    )

    assert responses[0].provider == "deepseek"
    assert responses[0].metadata["routing_fallback_from"] == "openai"
