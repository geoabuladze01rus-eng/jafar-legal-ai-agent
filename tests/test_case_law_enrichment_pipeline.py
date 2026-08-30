from __future__ import annotations

from datetime import date

from jafar.case_law_document import CaseLawDocument
from jafar.case_law_enrichment_pipeline import CaseLawEnrichmentPipeline
from jafar.case_law_sources import CaseLawSourceItem, SourceTrust


class FakeDocumentFetcher:
    def fetch(self, url: str) -> CaseLawDocument:
        return CaseLawDocument(
            url=url,
            text="Верховный Суд указал, что требования ст. 75 УПК РФ подлежат проверке при оценке доказательств.",
            raw_fingerprint="raw",
            text_fingerprint="text",
            content_type="text/html",
            etag=None,
            last_modified=None,
        )


def item(trust: SourceTrust) -> CaseLawSourceItem:
    return CaseLawSourceItem(
        external_id="1",
        citation="Определение ВС РФ",
        court="Верховный Суд Российской Федерации",
        decided_on=date(2026, 8, 28),
        topic="допустимость доказательств",
        proposition="candidate",
        source_url="https://example.test/doc",
        source_name="source",
        authority_id="authority-1",
        trust=trust,
    )


def test_enrichment_never_enters_ingestion_directly() -> None:
    result = CaseLawEnrichmentPipeline(document_fetcher=FakeDocumentFetcher()).enrich(
        item(SourceTrust.CANONICAL)
    )

    assert result.may_enter_canonical_verification is True
    assert result.may_enter_ingestion_directly is False
    assert result.authority_candidates


def test_discovery_source_does_not_supply_canonical_url_to_authority_candidate() -> None:
    result = CaseLawEnrichmentPipeline(document_fetcher=FakeDocumentFetcher()).enrich(
        item(SourceTrust.DISCOVERY)
    )

    assert all(candidate.source_url is None for candidate in result.authority_candidates)
