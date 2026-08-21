from dataclasses import dataclass
from typing import Protocol

from jafar.ai.report import LegalReport


@dataclass(frozen=True)
class StoredAnalysis:
    analysis_id: str
    matter_id: str | None
    document_id: str | None
    email_id: str | None
    analysis_type: str
    model: str | None
    result: dict
    citations: list[dict]


class AnalysisRepository(Protocol):
    def save(self, analysis: StoredAnalysis) -> None: ...


def report_to_record(
    report: LegalReport,
    *,
    analysis_id: str,
    matter_id: str | None = None,
    document_id: str | None = None,
    email_id: str | None = None,
    model: str | None = None,
) -> StoredAnalysis:
    return StoredAnalysis(
        analysis_id=analysis_id,
        matter_id=matter_id,
        document_id=document_id,
        email_id=email_id,
        analysis_type="legal_document_analysis",
        model=model,
        result={
            "summary": report.summary,
            "facts": report.facts,
            "risks": report.risks,
            "deadlines": report.deadlines,
            "missing_information": report.missing_information,
            "recommendations": report.recommendations,
        },
        citations=[
            {
                "chunk_id": citation.chunk_id,
                "source": citation.source,
                "page": getattr(citation, "page", None),
            }
            for citation in report.citations
        ],
    )
