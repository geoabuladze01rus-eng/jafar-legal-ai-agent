from __future__ import annotations

from datetime import datetime, timezone

import pytest

from jafar.ai_provider import AIProviderConfig, OpenAILegalAnalyzer
from jafar.domains import DocumentTask, MatterType
from jafar.legal_models import LegalAnalysis


class FakeResponses:
    def __init__(self, parsed):
        self.parsed = parsed
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return type("Response", (), {"output_parsed": self.parsed})()


class FakeClient:
    def __init__(self, parsed):
        self.responses = FakeResponses(parsed)


def make_analysis() -> LegalAnalysis:
    return LegalAnalysis(
        task=DocumentTask.LEGAL_ANALYSIS,
        matter_type=MatterType.GENERAL,
        summary="A supported summary.",
        generated_at=datetime.now(timezone.utc),
        confidence=0.8,
    )


def test_openai_adapter_returns_structured_analysis_without_exposing_key():
    client = FakeClient(make_analysis())
    analyzer = OpenAILegalAnalyzer(config=AIProviderConfig(model="test-model"), client=client)

    result = analyzer.analyze(
        text="The document states that the response is due on 1 September.",
        task=DocumentTask.LEGAL_ANALYSIS,
        matter_type=MatterType.GENERAL,
    )

    assert result.summary == "A supported summary."
    call = client.responses.calls[0]
    assert call["model"] == "test-model"
    assert call["text_format"] is LegalAnalysis
    assert "OPENAI_API_KEY" not in repr(call)


def test_openai_adapter_rejects_empty_structured_response():
    client = FakeClient(None)
    analyzer = OpenAILegalAnalyzer(config=AIProviderConfig(model="test-model"), client=client)

    with pytest.raises(RuntimeError, match="no structured legal analysis"):
        analyzer.analyze(
            text="Document text",
            task=DocumentTask.LEGAL_ANALYSIS,
            matter_type=MatterType.GENERAL,
        )
