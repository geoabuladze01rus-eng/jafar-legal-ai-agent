from __future__ import annotations

import hashlib
import os

from .ai_provider import AIProviderConfig, OpenAILegalAnalyzer
from .legal_models import AnalysisRequest, AnalysisResponse, LegalAnalysis
from .matter_intelligence_writer import MatterIntelligenceWriter
from .model_router import ModelRequest, ModelRouter


class LegalAnalysisService:
    """Application service connecting legal requests to the model router."""

    def __init__(self, router: ModelRouter, intelligence_writer: MatterIntelligenceWriter | None = None, owner_id: str = "local-development-user") -> None:
        self.router = router
        self.intelligence_writer = intelligence_writer
        self.owner_id = owner_id

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
            raise RuntimeError("AI provider returned no structured legal analysis")  # noqa: TRY004

        analysis = LegalAnalysis.model_validate(payload)
        persisted = False
        if self.intelligence_writer and request.matter_id:
            run_id = "analysis:" + hashlib.sha256(request.text.encode()).hexdigest()[:32]
            outcome = self.intelligence_writer.write(
                owner_id=self.owner_id,
                matter_id=request.matter_id,
                kind="position",
                payload={"draft": analysis.summary, "state": "DRAFT", "reviewed": False, "lawyer_approved": False, "issues": [item.model_dump(mode="json") for item in analysis.issues]},
                analysis_run_id=run_id,
            )
            persisted = outcome.status == "persisted"
        return AnalysisResponse(analysis=analysis, matter_id=request.matter_id, persisted=persisted)
