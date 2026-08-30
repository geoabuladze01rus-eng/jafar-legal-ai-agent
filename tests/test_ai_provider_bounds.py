from __future__ import annotations

from types import SimpleNamespace

import pytest

from jafar.ai_provider import AIProviderConfig, OpenAILegalAnalyzer
from jafar.domains import DocumentTask, MatterType
from jafar.legal_models import LegalAnalysis


class _Responses:
    def __init__(self) -> None:
        self.kwargs = None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            output_parsed=LegalAnalysis(
                task=DocumentTask.LEGAL_ANALYSIS,
                matter_type=MatterType.CRIMINAL,
                summary="ok",
            ),
            usage=SimpleNamespace(
                model_dump=lambda: {"input_tokens": 10, "output_tokens": 5}
            ),
        )


class _Client:
    def __init__(self) -> None:
        self.responses = _Responses()


def test_structured_provider_sends_explicit_output_token_ceiling() -> None:
    client = _Client()
    analyzer = OpenAILegalAnalyzer(
        config=AIProviderConfig(model="model-a", max_retries=0, max_output_tokens=1234),
        client=client,  # type: ignore[arg-type]
    )

    analysis, metadata = analyzer.analyze_with_usage(
        text="текст дела",
        task=DocumentTask.LEGAL_ANALYSIS,
        matter_type=MatterType.CRIMINAL,
    )

    assert analysis.summary == "ok"
    assert client.responses.kwargs["max_output_tokens"] == 1234
    assert metadata["usage"]["input_tokens"] == 10


def test_provider_config_rejects_unbounded_or_excessive_retry_settings() -> None:
    with pytest.raises(ValueError, match="max_output_tokens_out_of_range"):
        AIProviderConfig(max_output_tokens=0)
    with pytest.raises(ValueError, match="retries_out_of_range"):
        AIProviderConfig(max_retries=100)
