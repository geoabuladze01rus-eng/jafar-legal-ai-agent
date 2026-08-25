from __future__ import annotations

from jafar import main
from jafar.domains import DocumentTask, MatterType


class FailingAnalyzer:
    def analyze(self, *, text: str, task: DocumentTask, matter_type: MatterType):
        raise RuntimeError("provider unavailable")


class RecordingAnalyzer:
    def __init__(self) -> None:
        self.received_text: str | None = None

    def analyze(self, *, text: str, task: DocumentTask, matter_type: MatterType):
        self.received_text = text
        return main.heuristic_analyzer.analyze(text, task, matter_type)


def test_resilient_analyzer_falls_back_to_local_heuristics(monkeypatch) -> None:
    monkeypatch.setattr(main, "openai_analyzer", FailingAnalyzer())
    analyzer = main.ResilientLegalAnalyzer()

    result = analyzer.analyze(
        "Срок обжалования до 31.08.2026.",
        DocumentTask.LEGAL_ANALYSIS,
        MatterType.CRIMINAL,
    )

    assert result.summary
    assert result.matter_type == MatterType.CRIMINAL


def test_resilient_analyzer_passes_plain_text_to_provider(monkeypatch) -> None:
    provider = RecordingAnalyzer()
    monkeypatch.setattr(main, "openai_analyzer", provider)
    analyzer = main.ResilientLegalAnalyzer()

    analyzer.analyze(
        "Текст юридического документа",
        DocumentTask.LEGAL_ANALYSIS,
        MatterType.GENERAL,
    )

    assert provider.received_text == "Текст юридического документа"
    assert isinstance(provider.received_text, str)
