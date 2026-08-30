from datetime import date

from jafar.case_law_source_sync import CaseLawSourceSyncEngine, SourceSyncStatus
from jafar.case_law_sources import CaseLawSourceItem, SourceTrust


class Adapter:
    def __init__(self, name, trust, items):
        self.name = name
        self.trust = trust
        self.items = tuple(items)

    def fetch_since(self, since=None):
        return self.items


def item(*, source_name, trust, external_id, citation="Определение ВС РФ от 01.08.2026 № 1-КГ26-1"):
    return CaseLawSourceItem(
        external_id=external_id,
        citation=citation,
        court="Верховный Суд Российской Федерации",
        decided_on=date(2026, 8, 1),
        topic="допустимость доказательств",
        proposition="Позиция",
        source_url=f"https://example.test/{external_id}",
        source_name=source_name,
        authority_id=f"authority:{external_id}",
        trust=trust,
        raw_fingerprint=f"fingerprint:{source_name}:{external_id}",
    )


def test_discovery_item_matches_canonical_candidate_without_becoming_canonical():
    canonical = item(
        source_name="supreme_court_rf",
        trust=SourceTrust.CANONICAL,
        external_id="official-1",
    )
    discovery = item(
        source_name="sudact",
        trust=SourceTrust.DISCOVERY,
        external_id="agg-1",
    )

    report = CaseLawSourceSyncEngine().sync(
        (
            Adapter("supreme", SourceTrust.CANONICAL, [canonical]),
            Adapter("sudact", SourceTrust.DISCOVERY, [discovery]),
        )
    )

    matched = next(entry for entry in report.items if entry.item.source_name == "sudact")
    assert matched.status == SourceSyncStatus.MATCHED_TO_CANONICAL
    assert matched.canonical_match_id == "official-1"
    assert matched.item.trust == SourceTrust.DISCOVERY
    assert matched.requires_canonical_verification is True
    assert report.discovery_unmatched == ()


def test_unmatched_discovery_requires_review():
    discovery = item(
        source_name="sudact",
        trust=SourceTrust.DISCOVERY,
        external_id="agg-2",
        citation="Определение неизвестного суда от 02.08.2026 № 2",
    )

    report = CaseLawSourceSyncEngine().sync(
        (Adapter("sudact", SourceTrust.DISCOVERY, [discovery]),)
    )

    assert report.items[0].status == SourceSyncStatus.DISCOVERY_ONLY
    assert report.discovery_unmatched == (discovery,)
    assert report.requires_human_review is True


def test_duplicate_items_from_same_source_are_deduplicated():
    canonical = item(
        source_name="supreme_court_rf",
        trust=SourceTrust.CANONICAL,
        external_id="official-1",
    )

    report = CaseLawSourceSyncEngine().sync(
        (Adapter("supreme", SourceTrust.CANONICAL, [canonical, canonical]),)
    )

    statuses = [entry.status for entry in report.items]
    assert statuses.count(SourceSyncStatus.CANONICAL_CANDIDATE) == 1
    assert statuses.count(SourceSyncStatus.DUPLICATE_SOURCE_ITEM) == 1
    assert report.canonical_candidates == (canonical,)
