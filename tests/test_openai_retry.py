from __future__ import annotations

from types import SimpleNamespace

import pytest

from jafar import config as config_module
from jafar.ai_provider import AIProviderConfig, OpenAILegalAnalyzer
from jafar.domains import DocumentTask, MatterType
from jafar.legal_models import LegalAnalysis


class FlakyResponses:
    def __init__(self, parsed: LegalAnalysis, failures: int):
        self.parsed = parsed
        self.failures = failures
        self.calls = 0

    def parse(self, **kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("temporary provider failure")
        return SimpleNamespace(output_parsed=self.parsed)


class FakeClient:
    def __init__(self, responses):
        self.responses = responses


def test_retry_succeeds_after_transient_failure(monkeypatch) -> None:
    monkeypatch.setattr(config_module.settings, "openai_api_key", "test-only-secret")
    expected = LegalAnalysis(
        task=DocumentTask.LEGAL_ANALYSIS,
        matter_type=MatterType.GENERAL,
        summary="retry success",
        confidence=0.8,
    )
    responses = FlakyResponses(expected, failures=1)
    provider = OpenAILegalAnalyzer(
        config=AIProviderConfig(model="test-model", max_retries=2, retry_backoff_seconds=0),
        client=FakeClient(responses),
    )

    result = provider.analyze(text="valid legal document", task=DocumentTask.LEGAL_ANALYSIS)

    assert result == expected
    assert responses.calls == 2


def test_retry_stops_after_max_retries(monkeypatch) -> None:
    monkeypatch.setattr(config_module.settings, "openai_api_key", "test-only-secret")
    responses = FlakyResponses(
        LegalAnalysis(
            task=DocumentTask.LEGAL_ANALYSIS,
            matter_type=MatterType.GENERAL,
            summary="unused",
            confidence=0.1,
        ),
        failures=10,
    )
    provider = OpenAILegalAnalyzer(
        config=AIProviderConfig(model="test-model", max_retries=2, retry_backoff_seconds=0),
        client=FakeClient(responses),
    )

    with pytest.raises(RuntimeError, match="OpenAI legal analysis failed"):
        provider.analyze(text="valid legal document", task=DocumentTask.LEGAL_ANALYSIS)

    assert responses.calls == 3


def test_invalid_input_is_not_retried(monkeypatch) -> None:
    monkeypatch.setattr(config_module.settings, "openai_api_key", "test-only-secret")
    responses = FlakyResponses(
        LegalAnalysis(
            task=DocumentTask.LEGAL_ANALYSIS,
            matter_type=MatterType.GENERAL,
            summary="unused",
            confidence=0.1,
        ),
        failures=10,
    )
    provider = OpenAILegalAnalyzer(
        config=AIProviderConfig(model="test-model", max_retries=2, retry_backoff_seconds=0),
        client=FakeClient(responses),
    )

    with pytest.raises(ValueError, match="document text must not be empty"):
        provider.analyze(text="", task=DocumentTask.LEGAL_ANALYSIS)

    assert responses.calls == 0
