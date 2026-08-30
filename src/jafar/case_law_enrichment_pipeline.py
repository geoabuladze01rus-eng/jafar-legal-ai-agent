from __future__ import annotations

from dataclasses import dataclass

from .case_law_document import CaseLawDocumentFetcher
from .case_law_sources import CaseLawSourceItem, SourceTrust
from .legal_authority_verification import AuthorityCandidate
from .legal_proposition_extractor import CaseLawEnrichment, LegalPropositionExtractor


@dataclass(frozen=True, slots=True)
class EnrichedCaseLawCandidate:
    source_item: CaseLawSourceItem
    enrichment: CaseLawEnrichment
    authority_candidates: tuple[AuthorityCandidate, ...]
    may_enter_canonical_verification: bool
    may_enter_ingestion_directly: bool = False


class CaseLawEnrichmentPipeline:
    """Fetch and enrich a discovered case-law item without bypassing verification gates."""

    def __init__(
        self,
        *,
        document_fetcher: CaseLawDocumentFetcher,
        extractor: LegalPropositionExtractor | None = None,
    ) -> None:
        self.document_fetcher = document_fetcher
        self.extractor = extractor or LegalPropositionExtractor()

    def enrich(self, item: CaseLawSourceItem) -> EnrichedCaseLawCandidate:
        document = self.document_fetcher.fetch(item.source_url)
        enrichment = self.extractor.extract(document)
        authority_candidates = tuple(
            AuthorityCandidate(
                authority_id=f"{item.authority_id}:ref:{index}",
                citation=reference.raw_text,
                proposition=(
                    enrichment.proposition_candidates[0].text
                    if enrichment.proposition_candidates
                    else item.proposition
                ),
                source_url=item.source_url if item.trust == SourceTrust.CANONICAL else None,
                source_name=item.source_name,
                effective_date=None,
                retrieved_at=None,
            )
            for index, reference in enumerate(enrichment.legal_reference_candidates, start=1)
        )
        return EnrichedCaseLawCandidate(
            source_item=item,
            enrichment=enrichment,
            authority_candidates=authority_candidates,
            may_enter_canonical_verification=True,
            may_enter_ingestion_directly=False,
        )
