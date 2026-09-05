from __future__ import annotations

import pytest

from jafar import config as config_module
from jafar.ai_provider import AIProviderConfig, OpenAILegalAnalyzer
from jafar.domains import DocumentTask


class FakeClient:
    pass


def test_openai_provider_is_unavailable_without_runtime_key(monkeypatch) -> None:
    monkeypatch.setattr(config_module.settings, "openai_api_key", None)
    provider = OpenAILegalAnalyzer(config=AIProviderConfig(), client=FakeClient())
    assert provider.available() is False


def test_openai_provider_is_available_with_runtime_key(monkeypatch) -> None:
    monkeypatch.setattr(config_module.settings, "openai_api_key", "test-only-secret")
    provider = OpenAILegalAnalyzer(config=AIProviderConfig(), client=FakeClient())
    assert provider.available() is True


def test_openai_key_is_not_exposed_by_provider_config(monkeypatch) -> None:
    monkeypatch.setattr(config_module.settings, "openai_api_key", "test-only-secret")
    provider = OpenAILegalAnalyzer(config=AIProviderConfig(), client=FakeClient())
    assert "test-only-secret" not in repr(provider.config)
    assert "test-only-secret" not in repr(provider)


def test_openai_provider_does_not_surface_sdk_error_text() -> None:
    class FailingResponses:
        def parse(self, **kwargs):
            raise RuntimeError("synthetic-secret-must-not-escape")

    class FailingClient:
        responses = FailingResponses()

    provider = OpenAILegalAnalyzer(
        config=AIProviderConfig(max_retries=0),
        client=FailingClient(),
    )

    with pytest.raises(RuntimeError, match="failed after retries") as exc_info:
        provider.analyze(text="synthetic", task=DocumentTask.LEGAL_ANALYSIS)

    assert "synthetic-secret" not in str(exc_info.value)
