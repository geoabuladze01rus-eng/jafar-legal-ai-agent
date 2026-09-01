from __future__ import annotations

from datetime import UTC, datetime

from jafar.document_intake import ExtractedDocument
from jafar.document_workflow import DocumentWorkflow
from jafar.domains import DocumentTask, MatterType
from jafar.legal_analysis import LegalAnalyzer
from jafar.legal_models import Matter
from jafar.matters import MatterStore
from jafar.model_router import ModelRequest, ModelResponse, ModelRouter
from jafar.privacy_policy import ProviderPrivacyPolicy
from jafar.routed_legal_analyzer import RoutedLegalAnalyzer


class FakeOllamaProvider:
    key = "ollama"

    def __init__(self, *, available: bool = True) -> None:
        self._available = available
        self.requests: list[ModelRequest] = []

    def available(self) -> bool:
        return self._available

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        analysis = {
            "task": request.task,
            "matter_type": request.matter_type or MatterType.GENERAL.value,
            "summary": "Локальный анализ Ollama.",
            "issues": [],
            "deadlines": [],
            "key_facts": ["Факт подтвержден документом."],
            "missing_information": [],
            "confidence": 0.9,
        }
        return ModelResponse(
            provider=self.key,
            model="qwen3:4b",
            text=analysis["summary"],
            metadata={"legal_analysis": analysis, "local": True},
        )


def make_local_router(provider: FakeOllamaProvider) -> ModelRouter:
    return ModelRouter(
        {"ollama": provider},
        privacy_policy=ProviderPrivacyPolicy(confidential_providers=("ollama",)),
    )


def test_routed_analyzer_uses_local_provider_for_confidential_legal_text() -> None:
    provider = FakeOllamaProvider()
    analyzer = RoutedLegalAnalyzer(make_local_router(provider), LegalAnalyzer())

    analysis = analyzer.analyze(
        "Документ по уголовному делу.",
        DocumentTask.LEGAL_ANALYSIS,
        MatterType.CRIMINAL,
    )

    assert analysis.summary == "Локальный анализ Ollama."
    assert analysis.matter_type == MatterType.CRIMINAL
    assert len(provider.requests) == 1
    assert provider.requests[0].confidential is True
    assert provider.requests[0].matter_type == MatterType.CRIMINAL.value


def test_routed_analyzer_falls_back_when_local_provider_is_unavailable() -> None:
    provider = FakeOllamaProvider(available=False)
    analyzer = RoutedLegalAnalyzer(make_local_router(provider), LegalAnalyzer())

    analysis = analyzer.analyze(
        "Срок обжалования до 21.08.2026.",
        DocumentTask.LEGAL_ANALYSIS,
        MatterType.CIVIL,
    )

    assert analysis.summary != "Локальный анализ Ollama."
    assert provider.requests == []


def test_document_workflow_keeps_event_capture_when_analysis_comes_from_ollama() -> None:
    store = MatterStore()
    now = datetime.now(UTC)
    store.create(
        Matter(
            id="matter-1",
            title="Взыскание задолженности",
            matter_type=MatterType.CIVIL,
            client_name="ООО Альфа",
            opposing_party="ООО Бета",
            court_or_authority="Арбитражный суд Москвы",
            case_number="А40-12345/2026",
            created_at=now,
            updated_at=now,
        )
    )
    provider = FakeOllamaProvider()
    analyzer = RoutedLegalAnalyzer(make_local_router(provider), LegalAnalyzer())
    workflow = DocumentWorkflow(store, analyzer)

    result = workflow.process(
        "review.txt",
        ExtractedDocument(
            filename="review.txt",
            media_type="text/plain",
            text="По делу А40-12345/2026 представлен новый документ.",
        ),
        task=DocumentTask.LEGAL_ANALYSIS,
        matter_type=MatterType.GENERAL,
    )

    assert result.match is not None
    assert result.match.matter_id == "matter-1"
    assert result.analysis.summary == "Локальный анализ Ollama."
    assert result.event is not None
    assert result.event.description == "Локальный анализ Ollama."
    assert len(store.events("matter-1")) == 1
    assert provider.requests[0].matter_type == MatterType.CIVIL.value
