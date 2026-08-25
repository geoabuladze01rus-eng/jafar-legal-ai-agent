import pytest

from jafar.model_consensus import ModelConsensus
from jafar.model_router import ModelRequest, ModelResponse, ModelRouter


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


def routing_request(*, verification: bool = False) -> ModelRequest:
    """Synthetic routing tests are non-confidential by design.

    Confidential legal requests remain restricted by ProviderPrivacyPolicy and
    must not silently fall back to providers that are disallowed for client data.
    """
    return ModelRequest("p", "legal_analysis", verification=verification, confidential=False)


def test_router_prefers_openai_for_legal_analysis() -> None:
    providers = {
        "openai": FakeProvider("openai", "ok"),
        "gemini": FakeProvider("gemini", "vision"),
        "deepseek": FakeProvider("deepseek", "technical"),
    }
    decision = ModelRouter(providers).decide(routing_request())
    assert decision.primary == "openai"


def test_router_falls_back_when_primary_is_unavailable() -> None:
    providers = {
        "openai": FakeProvider("openai", "ok", available=False),
        "gemini": FakeProvider("gemini", "vision"),
        "deepseek": FakeProvider("deepseek", "technical"),
    }
    decision = ModelRouter(providers).decide(routing_request())
    assert decision.primary == "gemini"


def test_router_falls_back_when_primary_fails_at_runtime() -> None:
    providers = {
        "openai": FakeProvider("openai", "broken", error=RuntimeError("timeout")),
        "gemini": FakeProvider("gemini", "fallback"),
        "deepseek": FakeProvider("deepseek", "technical"),
    }
    result = ModelRouter(providers).run(routing_request())
    assert result[0].provider == "gemini"
    assert result[0].metadata["routing_fallback_from"] == "openai"


def test_verification_uses_independent_provider() -> None:
    providers = {
        "openai": FakeProvider("openai", "same conclusion"),
        "deepseek": FakeProvider("deepseek", "same conclusion"),
        "gemini": FakeProvider("gemini", "vision"),
    }
    result = ModelConsensus(ModelRouter(providers)).evaluate(routing_request(verification=True))
    assert result.primary.provider == "openai"
    assert result.verifier is not None
    assert result.verifier.provider == "deepseek"
    assert result.confidence == 0.85
    assert result.disagreements == ()


def test_verification_marks_disagreement_instead_of_hiding_it() -> None:
    providers = {
        "openai": FakeProvider("openai", "conclusion A"),
        "deepseek": FakeProvider("deepseek", "conclusion B"),
        "gemini": FakeProvider("gemini", "vision"),
    }
    result = ModelConsensus(ModelRouter(providers)).evaluate(routing_request(verification=True))
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
        ModelRouter(providers).decide(routing_request(verification=True))


def test_verifier_runtime_failure_is_not_silently_downgraded() -> None:
    providers = {
        "openai": FakeProvider("openai", "primary"),
        "deepseek": FakeProvider("deepseek", "broken", error=RuntimeError("timeout")),
    }
    with pytest.raises(RuntimeError, match="Independent verification provider"):
        ModelRouter(providers).run(routing_request(verification=True))
