from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .document_intake import ExtractedDocument
from .legal_analysis import LegalAnalyzer
from .legal_models import LegalAnalysis, Matter, MatterEvent
from .matter_matching import MatterMatch, MatterMatcher
from .matters import MatterStore


@dataclass(frozen=True)
class DocumentWorkflowResult:
    document_name: str
    extracted: ExtractedDocument
    match: MatterMatch | None
    analysis: LegalAnalysis
    event: MatterEvent | None


class DocumentWorkflow:
    """Orchestrates document extraction, matter matching, analysis and event capture."""

    def __init__(
        self,
        store: MatterStore,
        analyzer: LegalAnalyzer,
        matcher: MatterMatcher | None = None,
    ) -> None:
        self.store = store
        self.analyzer = analyzer
        self.matcher = matcher or MatterMatcher()

    def process(
        self,
        document_name: str,
        extracted: ExtractedDocument,
    ) -> DocumentWorkflowResult:
        matters = self.store.list_matters()
        match = self.matcher.best_match(extracted.text, matters)
        matter: Matter | None = self.store.get(match.matter_id) if match else None

        matter_type = matter.matter_type if matter else extracted.matter_type
        analysis = self.analyzer.analyze(extracted.text, extracted.task, matter_type)
        event = None

        if matter:
            self.store.add_deadlines(matter.id, analysis.deadlines)
            event = self.store.add_event(
                matter_id=matter.id,
                title=f"Анализ документа: {document_name}",
                event_date=datetime.now(timezone.utc),
                description=analysis.summary,
                source_document=document_name,
            )

        return DocumentWorkflowResult(
            document_name=document_name,
            extracted=extracted,
            match=match,
            analysis=analysis,
            event=event,
        )
