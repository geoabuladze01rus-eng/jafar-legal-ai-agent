from __future__ import annotations

from pydantic import ValidationError

from .domains import DocumentTask, MatterType
from .legal_analysis import LegalAnalyzer
from .legal_models import LegalAnalysis
from .model_router import ModelRequest, ModelRouter


class RoutedLegalAnalyzer:
    """Use the central model router while preserving deterministic fail-closed fallback."""

    def __init__(self, router: ModelRouter, fallback: LegalAnalyzer) -> None:
        self.router = router
        self.fallback = fallback

    def analyze(
        self,
        text: str,
        task: DocumentTask,
        matter_type: MatterType = MatterType.GENERAL,
    ) -> LegalAnalysis:
        request = ModelRequest(
            prompt=text,
            task=task.value,
            matter_type=matter_type.value,
            confidential=True,
        )
        try:
            responses = self.router.run(request)
        except RuntimeError:
            return self.fallback.analyze(text, task, matter_type)

        payload = responses[0].metadata.get("legal_analysis")
        if not isinstance(payload, dict):
            return self.fallback.analyze(text, task, matter_type)

        try:
            return LegalAnalysis.model_validate(payload)
        except ValidationError:
            return self.fallback.analyze(text, task, matter_type)
