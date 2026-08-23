from __future__ import annotations

from jafar.analysis_service import LegalAnalysisService
from jafar.domains import DocumentTask, MatterType
from jafar.legal_models import AnalysisRequest, LegalAnalysis
from jafar.model_router import ModelRequest, ModelResponse


class FakeProvider:
    key = "openai"

    def available(self) -> bool:
        return True

    def complete(self, request: ModelRequest) -> ModelResponse:
        analysis = LegalAnalysis(
            task=DocumentTask(request.task),
            matter_type=MatterType.GENERAL,
            summary="structured result",
            confidence=0.8,
        )
        return ModelResponse(
            provider=self.key,
            model="test-model",
            text=analysis.summary,
            metadata={"legal_analysis": analysis.model_dump(mode="json")},
        )


def test_analysis_service_returns_structured_analysis() -> None:
    from jafar.model_router import ModelRouter

    service = LegalAnalysisService(ModelRouter({"openai": FakeProvider()}))
    response = service.analyze(
        AnalysisRequest(text="Test legal document", task=DocumentTask.LEGAL_ANALYSIS)
    )

    assert response.analysis.summary == "structured result"
    assert response.analysis.confidence == 0.8
