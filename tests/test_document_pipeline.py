from datetime import datetime, timezone

from jafar.document_intake import DocumentExtractor
from jafar.document_pipeline import DocumentPipeline
from jafar.legal_models import LegalAnalysis, Matter
from jafar.matter_matching import MatterMatcher
from jafar.domains import DocumentTask, MatterType


class FakeAnalyzer:
    def analyze(self, text: str) -> LegalAnalysis:
        return LegalAnalysis(
            task=DocumentTask.LEGAL_ANALYSIS,
            matter_type=MatterType.GENERAL,
            summary=f"analyzed:{text}",
        )


def matter(case_number: str) -> Matter:
    now = datetime.now(timezone.utc)
    return Matter(
        id="matter-1",
        title="Павлик В.А.",
        matter_type=MatterType.GENERAL,
        client_name="Павлик В.А.",
        case_number=case_number,
        created_at=now,
        updated_at=now,
    )


def pipeline() -> DocumentPipeline:
    return DocumentPipeline(DocumentExtractor(), MatterMatcher(), FakeAnalyzer())


def test_pipeline_analyzes_only_after_confident_match():
    result = pipeline().process(
        "decision.txt",
        "Уголовное дело № 12604008104000012. Павлик В.А.".encode(),
        [matter("12604008104000012")],
        "text/plain",
    )
    assert result.status == "matched"
    assert result.match is not None
    assert result.analysis is not None
    assert result.document.fingerprint


def test_pipeline_fails_closed_for_unmatched_document():
    result = pipeline().process(
        "unknown.txt",
        "Документ без номера дела и без идентифицирующих данных".encode(),
        [matter("12604008104000012")],
        "text/plain",
    )
    assert result.status == "needs_matter_review"
    assert result.match is None
    assert result.analysis is None
