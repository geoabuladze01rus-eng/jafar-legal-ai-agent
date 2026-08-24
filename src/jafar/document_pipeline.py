from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .document_intake import DocumentExtractor, ExtractedDocument
from .legal_models import LegalAnalysis, Matter
from .matter_matching import MatterMatch, MatterMatcher


class LegalAnalyzer(Protocol):
    def analyze(self, text: str) -> LegalAnalysis: ...


@dataclass(frozen=True)
class DocumentPipelineResult:
    document: ExtractedDocument
    match: MatterMatch | None
    status: str
    analysis: LegalAnalysis | None = None


class DocumentPipeline:
    """Safe orchestration for incoming legal documents.

    Matching is deliberately separated from analysis and persistence. A weak
    or ambiguous matter match never gets silently attached to a case.
    """

    def __init__(
        self,
        extractor: DocumentExtractor,
        matcher: MatterMatcher,
        analyzer: LegalAnalyzer,
    ) -> None:
        self.extractor = extractor
        self.matcher = matcher
        self.analyzer = analyzer

    def process(
        self,
        filename: str,
        content: bytes,
        matters: list[Matter],
        media_type: str | None = None,
    ) -> DocumentPipelineResult:
        document = self.extractor.extract(filename, content, media_type)
        match = self.matcher.best_match(document.text, matters)
        if match is None:
            return DocumentPipelineResult(
                document=document,
                match=None,
                status="needs_matter_review",
            )

        analysis = self.analyzer.analyze(document.text)
        return DocumentPipelineResult(
            document=document,
            match=match,
            status="matched",
            analysis=analysis,
        )
