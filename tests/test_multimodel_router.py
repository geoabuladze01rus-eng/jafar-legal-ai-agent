import pytest

from jafar.model_consensus import ModelConsensus
from jafar.model_router import ModelRequest, ModelResponse, ModelRouter
from jafar.privacy_policy import ProviderPrivacyPolicy


class FakeProvider:
    def __init__(self, key: str, text: str, available: bool = True, error: Exception | None = None) -> None:
        self.key = key
        self.text = text
        self._available = available
        self.error = error
        self.calls = 0

    def available(self) -> bool:
        return self._available

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return ModelResponse(self.key, "test-model", self.text, {})


def local_policy(*, cloud_fallback: bool = False) -> ProviderPrivacyPolicy:
    providers = ("ollama", "openai") if cloud_fallback else ("ollama",)
    return ProviderPrivacyPolicy(confidential_providers=providers)


def test_router_prefers_ollama_for_confidential_text() -> None:
    providers = {
        "ollama": FakeProvider("ollama", "local"),
        "openai": FakeProvider("openai", "cloud"),
    }
    decision = ModelRouter(providers, privacy_policy=local_policy()).decide(
        ModelRequest("p", "legal_analysis")
    )
    assert decision.primary == "ollama"


def test_router_fails_closed_when_local_model_is_unavailable() -> None:
    providers = {
        "ollama": FakeProvider("ollama", "local", available=False),
        "openai": FakeProvider("openai", "cloud"),
    }
    with pytest.raises(RuntimeError, match="No permitted and available AI provider"):
        ModelRouter(providers, privacy_policy=local_policy()).decide(
            ModelRequest("p", "legal_analysis")
        )


def test_router_uses_openai_fallback_only_when_confidential_cloud_is_opted_in() -> None:
    providers = {
        "ollama": FakeProvider("ollama", "local", available=False),
        "openai": FakeProvider("openai", "cloud"),
    }
    router = ModelRouter(providers, privacy_policy=local_policy(cloud_fallback=True))
    decision = router.decide(ModelRequest("p", "legal_analysis"))
    assert decision.primary == "openai"


def test_router_prefers_openai_for_non_confidential_legal_analysis() -> None:
    providers = {
        "ollama": FakeProvider("ollama", "local"),
        "openai": FakeProvider("openai", "ok"),
        "gemini": FakeProvider("gemini", "vision"),
        "deepseek": FakeProvider("deepseek", "technical"),
    }
    decision = ModelRouter(providers).decide(
        ModelRequest("p", "legal_analysis", confidential=False)
    )
    assert decision.primary == "openai"


def test_router_falls_back_when_primary_is_unavailable() -> None:
    providers = {
        "openai": FakeProvider("openai", "ok", available=False),
        "gemini": FakeProvider("gemini", "vision"),
        "deepseek": FakeProvider("deepseek", "technical"),
    }
    decision = ModelRouter(providers).decide(
        ModelRequest("p", "legal_analysis", confidential=False)
    )
    assert decision.primary == "gemini"


def test_router_falls_back_when_primary_fails_at_runtime() -> None:
    providers = {
        "openai": FakeProvider("openai", "broken", error=RuntimeError("timeout")),
        "gemini": FakeProvider("gemini", "fallback"),
        "deepseek": FakeProvider("deepseek", "technical"),
    }
    result = ModelRouter(providers).run(
        ModelRequest("p", "legal_analysis", confidential=False)
    )
    assert result[0].provider == "gemini"
    assert result[0].metadata["routing_fallback_from"] == "openai"


def test_verification_uses_independent_provider() -> None:
    providers = {
        "openai": FakeProvider("openai", "same conclusion"),
        "deepseek": FakeProvider("deepseek", "same conclusion"),
        "gemini": FakeProvider("gemini", "vision"),
    }
    result = ModelConsensus(ModelRouter(providers)).evaluate(
        ModelRequest("p", "legal_analysis", verification=True, confidential=False)
    )
    assert result.primary.provider == "openai"
    assert result.verifier is not None
    assert result.verifier.provider == "deepseek"
    assert result.confidence == 0.85
    assert result.disagreements == ()


def test_confidential_verification_requires_cloud_opt_in() -> None:
    providers = {
        "ollama": FakeProvider("ollama", "same conclusion"),
        "openai": FakeProvider("openai", "same conclusion"),
    }
    with pytest.raises(RuntimeError, match="Verification requested"):
        ModelRouter(providers, privacy_policy=local_policy()).decide(
            ModelRequest("p", "legal_analysis", verification=True)
        )


def test_confidential_verification_can_use_openai_after_explicit_opt_in() -> None:
    providers = {
        "ollama": FakeProvider("ollama", "same conclusion"),
        "openai": FakeProvider("openai", "same conclusion"),
    }
    router = ModelRouter(providers, privacy_policy=local_policy(cloud_fallback=True))
    result = ModelConsensus(router).evaluate(
        ModelRequest("p", "legal_analysis", verification=True)
    )
    assert result.primary.provider == "ollama"
    assert result.verifier is not None
    assert result.verifier.provider == "openai"


def test_verification_marks_disagreement_instead_of_hiding_it() -> None:
    providers = {
        "openai": FakeProvider("openai", "conclusion A"),
        "deepseek": FakeProvider("deepseek", "conclusion B"),
        "gemini": FakeProvider("gemini", "vision"),
    }
    result = ModelConsensus(ModelRouter(providers)).evaluate(
        ModelRequest("p", "legal_analysis", verification=True, confidential=False)
    )
    assert result.verifier is not None
    assert result.confidence == 0.45
    assert result.disagreements
    assert "требует проверки" in result.consensus


def test_requested_verification_fails_closed_when_verifier_unavailable() -> None:
    providers = {
        "openai": FakeProvider("openai", "primary"),
        "deepseek": FakeProvider("deepseek", "unavailable", available=False),
    }
    with pytest.raises(RuntimeError, match="Verification requested"):
        ModelRouter(providers).decide(
            ModelRequest("p", "legal_analysis", verification=True, confidential=False)
        )


def test_verifier_runtime_failure_is_not_silently_downgraded() -> None:
    providers = {
        "openai": FakeProvider("openai", "primary"),
        "deepseek": FakeProvider("deepseek", "broken", error=RuntimeError("timeout")),
    }
    with pytest.raises(RuntimeError, match="Independent verification provider"):
        ModelRouter(providers).run(
            ModelRequest("p", "legal_analysis", verification=True, confidential=False)
        )
