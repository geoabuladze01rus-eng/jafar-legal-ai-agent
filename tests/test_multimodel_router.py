from jafar.model_consensus import ModelConsensus
from jafar.model_router import ModelRequest, ModelResponse, ModelRouter


class FakeProvider:
    def __init__(self, key: str, text: str, available: bool = True) -> None:
        self.key = key
        self.text = text
        self._available = available
        self.calls = 0

    def available(self) -> bool:
        return self._available

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        return ModelResponse(self.key, "test-model", self.text, {})


def test_router_prefers_openai_for_legal_analysis() -> None:
    providers = {
        "openai": FakeProvider("openai", "ok"),
        "gemini": FakeProvider("gemini", "vision"),
        "deepseek": FakeProvider("deepseek", "technical"),
    }
    decision = ModelRouter(providers).decide(ModelRequest("p", "legal_analysis"))
    assert decision.primary == "openai"


def test_router_falls_back_when_primary_is_unavailable() -> None:
    providers = {
        "openai": FakeProvider("openai", "ok", available=False),
        "gemini": FakeProvider("gemini", "vision"),
        "deepseek": FakeProvider("deepseek", "technical"),
    }
    decision = ModelRouter(providers).decide(ModelRequest("p", "legal_analysis"))
    assert decision.primary == "gemini"


def test_verification_uses_independent_provider() -> None:
    providers = {
        "openai": FakeProvider("openai", "same conclusion"),
        "deepseek": FakeProvider("deepseek", "same conclusion"),
        "gemini": FakeProvider("gemini", "vision"),
    }
    result = ModelConsensus(ModelRouter(providers)).evaluate(
        ModelRequest("p", "legal_analysis", verification=True)
    )
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
    result = ModelConsensus(ModelRouter(providers)).evaluate(
        ModelRequest("p", "legal_analysis", verification=True)
    )
    assert result.verifier is not None
    assert result.confidence == 0.45
    assert result.disagreements
    assert "требует проверки" in result.consensus
