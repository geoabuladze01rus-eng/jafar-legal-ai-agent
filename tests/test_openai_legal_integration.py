from __future__ import annotations

from types import SimpleNamespace

from jafar import config as config_module
from jafar.ai_provider import AIProviderConfig, OpenAILegalAnalyzer
from jafar.domains import DocumentTask, MatterType
from jafar.legal_models import LegalAnalysis


class FakeResponses:
    def __init__(self, parsed: LegalAnalysis):
        self.parsed = parsed
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self.parsed)


class FakeClient:
    def __init__(self, parsed: LegalAnalysis):
        self.responses = FakeResponses(parsed)


def test_openai_structured_legal_analysis_contract(monkeypatch) -> None:
    monkeypatch.setattr(config_module.settings, "openai_api_key", "test-only-secret")
    expected = LegalAnalysis(
        task=DocumentTask.LEGAL_ANALYSIS,
        matter_type=MatterType.GENERAL,
        summary="The document requires review of the stated legal issues.",
        confidence=0.82,
    )
    client = FakeClient(expected)
    provider = OpenAILegalAnalyzer(
        config=AIProviderConfig(model="test-model"),
        client=client,
    )

    result = provider.analyze(
        text="A document containing legally relevant facts.",
        task=DocumentTask.LEGAL_ANALYSIS,
        matter_type=MatterType.GENERAL,
    )

    assert result == expected
    assert client.responses.calls[0]["model"] == "test-model"
    assert client.responses.calls[0]["text_format"] is LegalAnalysis
    assert client.responses.calls[0]["input"][0]["role"] == "system"
    assert "test-only-secret" not in repr(client.responses.calls)
