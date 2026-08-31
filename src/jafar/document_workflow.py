from __future__ import annotations

from dataclasses import dataclass
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


class DocumentWorkflow:
    """Analyze untrusted documents without persisting conclusions until lawyer approval."""

    def __init__(self, store: MatterRepository, analyzer: LegalAnalyzer,
                 matcher: MatterMatcher | None = None) -> None:
        self.store = store
        self.analyzer = analyzer
        self.matcher = matcher or MatterMatcher()

    def process(self, document_name: str, extracted: ExtractedDocument,
                task: DocumentTask = DocumentTask.LEGAL_ANALYSIS,
                matter_type: MatterType = MatterType.GENERAL) -> DocumentWorkflowResult:
        match = self.matcher.best_match(extracted.text, self.store.list_matters())
        matter = self.store.get(match.matter_id) if match else None
        effective_type = matter.matter_type if matter else matter_type
        analysis = self.analyzer.analyze(extracted.text, task, effective_type)
        return DocumentWorkflowResult(document_name=document_name, extracted=extracted,
                                      match=match, analysis=analysis, event=None)
