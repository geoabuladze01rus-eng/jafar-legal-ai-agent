import pytest

from jafar.ai_council import AICouncil
from jafar.model_router import ModelRequest, ModelResponse
from jafar.privacy_policy import ProviderPrivacyPolicy


class FakeProvider:
    def __init__(self, key: str, text: str, available: bool = True, error: Exception | None = None) -> None:
        self.key = key
        self.text = text
        self._available = available
        self.error = error

    def available(self) -> bool:
        return self._available

    def complete(self, request: ModelRequest) -> ModelResponse:
        if self.error is not None:
            raise self.error
        return ModelResponse(self.key, "test-model", self.text, {})


def test_ai_council_runs_four_independent_models_when_allowed() -> None:
    providers = {
        "openai": FakeProvider("openai", "A"),
        "qwen": FakeProvider("qwen", "B"),
        "kimi": FakeProvider("kimi", "C"),
        "deepseek": FakeProvider("deepseek", "D"),
    }
    result = AICouncil(providers).run(
        ModelRequest(
            "analyze",
            "legal_analysis",
            confidential=False,
            allowed_providers=("openai", "qwen", "kimi", "deepseek"),
        ),
        minimum_responses=4,
    )
    assert result.providers == ("openai", "qwen", "kimi", "deepseek")
    assert result.disagreements


def test_ai_council_preserves_agreement_without_fake_disagreement() -> None:
    providers = {
        "openai": FakeProvider("openai", "same conclusion"),
        "qwen": FakeProvider("qwen", "same conclusion"),
    }
    result = AICouncil(providers).run(
        ModelRequest(
            "analyze",
            "legal_analysis",
            confidential=False,
            allowed_providers=("openai", "qwen"),
        )
    )
    assert result.disagreements == ()


def test_ai_council_fails_closed_when_not_enough_models_succeed() -> None:
    providers = {
        "openai": FakeProvider("openai", "A"),
        "qwen": FakeProvider("qwen", "B", error=RuntimeError("timeout")),
    }
    with pytest.raises(RuntimeError, match="requires at least 2"):
        AICouncil(providers).run(
            ModelRequest(
                "analyze",
                "legal_analysis",
                confidential=False,
                allowed_providers=("openai", "qwen"),
            )
        )


def test_confidential_council_requires_explicit_trusted_policy() -> None:
    providers = {
        "openai": FakeProvider("openai", "A"),
        "qwen": FakeProvider("qwen", "B"),
    }
    with pytest.raises(PermissionError):
        AICouncil(providers).run(
            ModelRequest(
                "secret case",
                "legal_analysis",
                confidential=True,
                allowed_providers=("openai", "qwen"),
            )
        )

    trusted = ProviderPrivacyPolicy(confidential_providers=("openai", "qwen"))
    result = AICouncil(providers, privacy_policy=trusted).run(
        ModelRequest(
            "secret case",
            "legal_analysis",
            confidential=True,
            allowed_providers=("openai", "qwen"),
        )
    )
    assert result.providers == ("openai", "qwen")
