from __future__ import annotations

import os

from .ai_provider import AIProviderConfig, OpenAILegalAnalyzer
from .legal_models import AnalysisRequest, AnalysisResponse, LegalAnalysis
from .model_router import ModelRequest, ModelRouter


class LegalAnalysisService:
    """Application service connecting legal requests to the model router."""

    def __init__(self, router: ModelRouter) -> None:
        self.router = router

    @classmethod
    def from_environment(cls) -> LegalAnalysisService:
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required to create the legal analysis service")

        model = os.environ.get("MODEL_NAME", "gpt-5.6")
        openai_provider = OpenAILegalAnalyzer(config=AIProviderConfig(model=model))
        return cls(ModelRouter(providers={openai_provider.key: openai_provider}))

    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        routed = self.router.run(
            ModelRequest(
                prompt=request.text,
                task=request.task.value,
            )
        )
        primary = routed[0]
        payload = primary.metadata.get("legal_analysis")
        if not isinstance(payload, dict):
            raise RuntimeError(  # noqa: TRY004 - this is a provider contract failure.
                "AI provider returned no structured legal analysis"
            )

        analysis = LegalAnalysis.model_validate(payload)
        return AnalysisResponse(analysis=analysis, matter_id=request.matter_id)
