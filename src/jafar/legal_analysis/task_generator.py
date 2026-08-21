from dataclasses import dataclass
from datetime import datetime

from jafar.legal_analysis.models import LegalAnalysisResult


@dataclass(frozen=True)
class GeneratedTaskProposal:
    task_id: str
    title: str
    description: str
    matter_id: str | None
    source_document_id: str
    due_at: datetime | None
    confidence: float
    requires_approval: bool = True


def generate_task_proposals(
    analysis: LegalAnalysisResult,
    matter_id: str | None = None,
) -> tuple[GeneratedTaskProposal, ...]:
    proposals: list[GeneratedTaskProposal] = []
    for index, recommendation in enumerate(analysis.recommendations):
        if not recommendation.strip():
            continue
        proposals.append(GeneratedTaskProposal(
            task_id=f"legal-proposal-{analysis.document_id}-{index}",
            title=recommendation.strip(),
            description=f"Предложено Джафаром по результатам анализа документа {analysis.document_id}.",
            matter_id=matter_id,
            source_document_id=analysis.document_id,
            due_at=None,
            confidence=analysis.confidence,
        ))
    return tuple(proposals)
