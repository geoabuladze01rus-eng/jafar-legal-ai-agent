from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .contradiction_detector import Contradiction, ContradictionGapDetector
from .matter_rag import MatterChunk


@dataclass(frozen=True, slots=True)
class DocumentClaim:
    matter_id: str
    document_id: str
    source_page: int
    chunk_index: int
    topic: str
    statement: str
    position: str

    @property
    def evidence_id(self) -> str:
        return f"document:{self.document_id}:page:{self.source_page}:chunk:{self.chunk_index}"

    def as_detector_claim(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "statement": self.statement,
            "position": self.position,
            "evidence_ids": [self.evidence_id],
        }


@dataclass(frozen=True, slots=True)
class CrossDocumentReport:
    matter_id: str
    contradictions: tuple[Contradiction, ...]
    documents_considered: tuple[str, ...]


class CrossDocumentContradictionService:
    """Compare claims only inside one legal matter and preserve source citations."""

    def __init__(self, detector: ContradictionGapDetector | None = None) -> None:
        self.detector = detector or ContradictionGapDetector()

    def compare(
        self,
        *,
        matter_id: str,
        claims: Iterable[DocumentClaim],
    ) -> CrossDocumentReport:
        scoped = [claim for claim in claims if claim.matter_id == matter_id]
        documents = tuple(sorted({claim.document_id for claim in scoped}))
        detector_claims = [claim.as_detector_claim() for claim in scoped]
        contradictions = tuple(self.detector.compare_claims(detector_claims))
        return CrossDocumentReport(
            matter_id=matter_id,
            contradictions=contradictions,
            documents_considered=documents,
        )

    @staticmethod
    def claims_from_chunks(
        *,
        chunks: Iterable[MatterChunk],
        topic: str,
        position: str,
    ) -> tuple[DocumentClaim, ...]:
        return tuple(
            DocumentClaim(
                matter_id=chunk.matter_id,
                document_id=chunk.document_id,
                source_page=chunk.source_page,
                chunk_index=chunk.chunk_index,
                topic=topic,
                statement=chunk.content,
                position=position,
            )
            for chunk in chunks
            if chunk.content.strip()
        )
