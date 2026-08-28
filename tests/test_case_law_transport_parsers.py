from __future__ import annotations

from datetime import date

from jafar.case_law_parsers import LinkBasedCaseLawParser
from jafar.case_law_sources import SourceTrust
from jafar.case_law_transport import HttpFetchResult


def fetched(body: str) -> HttpFetchResult:
    return HttpFetchResult(
        url="https://example.test/list",
        status_code=200,
        body=body.encode("utf-8"),
        content_type="text/html; charset=utf-8",
        etag="etag-1",
        last_modified="Fri, 28 Aug 2026 10:00:00 GMT",
        retrieved_at_monotonic=1.0,
    )


def test_parser_extracts_case_law_links_and_provenance() -> None:
    parser = LinkBasedCaseLawParser(
        source_name="supreme_court_rf",
        trust=SourceTrust.CANONICAL,
        court="Верховный Суд Российской Федерации",
    )
    page = parser.parse(
        fetched('<a href="/doc/1">Определение от 28.08.2026 по делу № 1</a>')
    )
    assert len(page.items) == 1
    assert page.items[0].trust == SourceTrust.CANONICAL
    assert page.items[0].decided_on == date(2026, 8, 28)
    assert page.items[0].source_url == "https://example.test/doc/1"
    assert page.provenance.body_fingerprint


def test_parser_ignores_non_case_links() -> None:
    parser = LinkBasedCaseLawParser(
        source_name="sudact",
        trust=SourceTrust.DISCOVERY,
        court="Верховный Суд Российской Федерации",
    )
    page = parser.parse(fetched('<a href="/news">Новости</a>'))
    assert page.items == ()


def test_discovery_parser_preserves_discovery_trust() -> None:
    parser = LinkBasedCaseLawParser(
        source_name="sudact",
        trust=SourceTrust.DISCOVERY,
        court="Верховный Суд Российской Федерации",
    )
    page = parser.parse(
        fetched('<a href="/vsrf/doc/1">Постановление от 28.08.2026</a>')
    )
    assert page.items[0].trust == SourceTrust.DISCOVERY
