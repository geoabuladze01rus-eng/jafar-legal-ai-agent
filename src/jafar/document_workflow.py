from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .council_review import CouncilReview, CouncilReviewService
from .document_intake import ExtractedDocument
from .domains import DocumentTask, MatterType
from .legal_analysis import LegalAnalyzer
from .legal_models import LegalAnalysis, MatterEvent
from .matter_matching import MatterMatch, MatterMatcher
from .matter_repository import MatterRepository


@dataclass(frozen=True)
class DocumentWorkflowResult:
    document_name: str
    extracted: ExtractedDocument
    match: MatterMatch | None
    analysis: LegalAnalysis
    event: MatterEvent | None
    council_review: CouncilReview | None = None


class DocumentWorkflow:
    """Orchestrates extraction, matter matching, deterministic analysis and optional AI review."""

    def __init__(
        self,
        store: MatterRepository,
        analyzer: LegalAnalyzer,
        matcher: MatterMatcher | None = None,
        council_review_service: CouncilReviewService | None = None,
    ) -> None:
        self.store = store
        self.analyzer = analyzer
        self.matcher = matcher or MatterMatcher()
        self.council_review_service = council_review_service

    def process(
        self,
        document_name: str,
        extracted: ExtractedDocument,
        task: DocumentTask = DocumentTask.LEGAL_ANALYSIS,
        matter_type: MatterType = MatterType.GENERAL,
        *,
        run_council_review: bool = False,
        confidential: bool = True,
        allowed_providers: tuple[str, ...] | None = None,
        council_minimum_responses: int = 2,
    ) -> DocumentWorkflowResult:
        match = self.matcher.best_match(extracted.text, self.store.list_matters())
        matter = self.store.get(match.matter_id) if match else None
        effective_type = matter.matter_type if matter else matter_type
        analysis = self.analyzer.analyze(extracted.text, task, effective_type)

        council_review = None
        if run_council_review:
            if self.council_review_service is None:
                raise RuntimeError("AI Council review requested but no CouncilReviewService is configured")
            council_review = self.council_review_service.review(
                document_text=extracted.text,
                analysis=analysis,
                confidential=confidential,
                allowed_providers=allowed_providers,
                minimum_responses=council_minimum_responses,
            )

        event = None
        if matter:
            event = self.store.record_document_event(
                matter_id=matter.id,
                title=f"Анализ документа: {document_name}",
                event_date=datetime.now(timezone.utc),
                description=analysis.summary,
                source_document=document_name,
                document_fingerprint=extracted.fingerprint,
                deadlines=analysis.deadlines,
            )

        return DocumentWorkflowResult(
            document_name=document_name,
            extracted=extracted,
            match=match,
            analysis=analysis,
            event=event,
            council_review=council_review,
        )
