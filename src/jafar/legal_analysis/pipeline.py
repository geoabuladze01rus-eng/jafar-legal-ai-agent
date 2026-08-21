from dataclasses import dataclass
from datetime import date
import re

from jafar.deadlines.extractor import DeadlineProposal
from jafar.legal_analysis.analyzer import LegalAnalyzer
from jafar.legal_analysis.models import LegalAnalysisResult


@dataclass(frozen=True)
class LegalDocumentPipelineResult:
    analysis: LegalAnalysisResult
    deadline_proposals: tuple[DeadlineProposal, ...]


class LegalDocumentPipeline:
    def __init__(self, analyzer: LegalAnalyzer):
        self.analyzer = analyzer

    async def process(self, document_id: str, text: str) -> LegalDocumentPipelineResult:
        analysis = await self.analyzer.analyze(document_id, text)
        proposals: list[DeadlineProposal] = []
        for raw in analysis.deadlines:
            match = re.search(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})", raw)
            if not match:
                continue
            day, month, year = map(int, match.groups())
            if year < 100:
                year += 2000
            try:
                due_date = date(year, month, day)
            except ValueError:
                continue
            proposals.append(DeadlineProposal(
                source_id=document_id,
                due_date=due_date,
                basis=raw,
                confidence=analysis.confidence,
                requires_approval=True,
            ))
        return LegalDocumentPipelineResult(analysis, tuple(proposals))
