from datetime import date

import pytest

from jafar.case_law_sources import (
    CaseLawSourceItem,
    CaseLawSourcePolicy,
    SourceTrust,
    SudactDiscoveryAdapter,
    SupremeCourtSourceAdapter,
)


class StubFetcher:
    def __init__(self, items):
        self.items = tuple(items)
        self.seen_since = None

    def fetch_since(self, since=None):
        self.seen_since = since
        return self.items


def item(*, trust=SourceTrust.DISCOVERY, source_name="raw"):
    return CaseLawSourceItem(
        external_id="123",
        citation="Определение ВС РФ от 01.08.2026 № 1-КГ26-1",
        court="Верховный Суд Российской Федерации",
        decided_on=date(2026, 8, 1),
        topic="допустимость доказательств",
        proposition="Проверяемая правовая позиция",
        source_url="https://example.test/123",
        source_name=source_name,
        authority_id="authority:123",
        trust=trust,
    )


def test_supreme_court_adapter_marks_items_as_canonical_candidates():
    fetcher = StubFetcher([item()])
    adapter = SupremeCourtSourceAdapter(fetcher)

    result = adapter.fetch_since(date(2026, 7, 1))

    assert result[0].trust == SourceTrust.CANONICAL
    assert result[0].source_name == "supreme_court_rf"
    assert fetcher.seen_since == date(2026, 7, 1)
    decision = CaseLawSourcePolicy.evaluate(result[0])
    assert decision.may_supply_canonical_provenance is True


def test_sudact_adapter_is_discovery_only():
    adapter = SudactDiscoveryAdapter(StubFetcher([item(trust=SourceTrust.CANONICAL)]))

    result = adapter.fetch_since()

    assert result[0].trust == SourceTrust.DISCOVERY
    assert result[0].source_name == "sudact"
    decision = CaseLawSourcePolicy.evaluate(result[0])
    assert decision.may_enter_verification is True
    assert decision.may_supply_canonical_provenance is False


def test_discovery_item_cannot_be_promoted_directly_to_case_law_record():
    discovery = item(trust=SourceTrust.DISCOVERY)

    with pytest.raises(ValueError, match="Discovery-only"):
        CaseLawSourcePolicy.to_case_law_record(
            discovery,
            canonical_fingerprint="fingerprint",
        )


def test_canonical_item_requires_verified_fingerprint_before_record_creation():
    canonical = item(trust=SourceTrust.CANONICAL)

    with pytest.raises(ValueError, match="canonical_fingerprint"):
        CaseLawSourcePolicy.to_case_law_record(canonical, canonical_fingerprint="")


def test_canonical_item_converts_only_after_fingerprint_is_supplied():
    canonical = item(trust=SourceTrust.CANONICAL)

    record = CaseLawSourcePolicy.to_case_law_record(
        canonical,
        canonical_fingerprint="canonical-sha256",
    )

    assert record.authority_id == canonical.authority_id
    assert record.source_fingerprint == "canonical-sha256"
    assert record.source_url == canonical.source_url
