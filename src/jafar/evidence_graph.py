from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .document_intake import ExtractedDocument


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    evidence_id: str
    document_name: str
    document_fingerprint: str
    excerpt: str
    page: int | None = None
    actor: str | None = None
    event_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EvidenceClaim:
    claim_id: str
    topic: str
    statement: str
    position: str
    provider: str
    evidence_ids: tuple[str, ...]
    supported: bool


class CaseEvidenceGraph:
    """Link model review claims to concrete evidence sources without promoting claims to facts."""

    def __init__(self) -> None:
        self._sources: dict[str, EvidenceSource] = {}
        self._claims: dict[str, EvidenceClaim] = {}

    def add_source(self, source: EvidenceSource) -> None:
        self._sources[source.evidence_id] = source

    def add_document_fragments(
        self,
        document: ExtractedDocument,
        *,
        document_name: str | None = None,
        actor: str | None = None,
        event_id: str | None = None,
        max_chars: int = 2_000,
    ) -> tuple[EvidenceSource, ...]:
        sources: list[EvidenceSource] = []
        for fragment in document.fragments(max_chars=max_chars):
            source = EvidenceSource(
                evidence_id=document.evidence_id(fragment),
                document_name=document_name or document.filename,
                document_fingerprint=document.fingerprint,
                excerpt=fragment.text,
                page=fragment.page,
                actor=actor,
                event_id=event_id,
                metadata={"chunk_index": fragment.chunk_index},
            )
            self.add_source(source)
            sources.append(source)
        return tuple(sources)

    def add_claim(
        self,
        *,
        claim_id: str,
        topic: str,
        statement: str,
        position: str,
        provider: str,
        evidence_ids: tuple[str, ...],
    ) -> EvidenceClaim:
        supported = bool(evidence_ids) and all(item in self._sources for item in evidence_ids)
        claim = EvidenceClaim(
            claim_id=claim_id,
            topic=topic,
            statement=statement,
            position=position,
            provider=provider,
            evidence_ids=evidence_ids,
            supported=supported,
        )
        self._claims[claim_id] = claim
        return claim

    def source(self, evidence_id: str) -> EvidenceSource | None:
        return self._sources.get(evidence_id)

    def claim(self, claim_id: str) -> EvidenceClaim | None:
        return self._claims.get(claim_id)

    def claims(self) -> tuple[EvidenceClaim, ...]:
        return tuple(self._claims.values())

    def sources(self) -> tuple[EvidenceSource, ...]:
        return tuple(self._sources.values())

    def unsupported_claims(self) -> tuple[EvidenceClaim, ...]:
        return tuple(claim for claim in self._claims.values() if not claim.supported)

    def snapshot(self) -> dict[str, Any]:
        return {
            "sources": [self._serialize_source(item) for item in self._sources.values()],
            "claims": [self._serialize_claim(item) for item in self._claims.values()],
            "requires_human_review": bool(self.unsupported_claims()),
        }

    @staticmethod
    def _serialize_source(source: EvidenceSource) -> dict[str, Any]:
        return {
            "evidence_id": source.evidence_id,
            "document_name": source.document_name,
            "document_fingerprint": source.document_fingerprint,
            "excerpt": source.excerpt,
            "page": source.page,
            "actor": source.actor,
            "event_id": source.event_id,
            "metadata": source.metadata,
        }

    @staticmethod
    def _serialize_claim(claim: EvidenceClaim) -> dict[str, Any]:
        return {
            "claim_id": claim.claim_id,
            "topic": claim.topic,
            "statement": claim.statement,
            "position": claim.position,
            "provider": claim.provider,
            "evidence_ids": list(claim.evidence_ids),
            "supported": claim.supported,
        }
