from __future__ import annotations

from jafar.case_law_document import CaseLawDocumentFetcher, HtmlDocumentTextExtractor
from jafar.case_law_transport import HttpFetchResult


class FakeTransport:
    def get(self, url: str) -> HttpFetchResult:
        return HttpFetchResult(
            url=url,
            status_code=200,
            body=b"<html><body><h1>Decision</h1><p>Court text</p><script>ignore()</script></body></html>",
            content_type="text/html; charset=utf-8",
            etag="etag-1",
            last_modified="Fri, 28 Aug 2026 10:00:00 GMT",
            retrieved_at_monotonic=1.0,
        )


def test_fetch_preserves_raw_and_text_fingerprints() -> None:
    document = CaseLawDocumentFetcher(FakeTransport()).fetch("https://example.test/doc")

    assert document.raw_fingerprint
    assert document.text_fingerprint
    assert document.raw_fingerprint != document.text_fingerprint
    assert "Court text" in document.text
    assert "ignore" not in document.text
    assert document.etag == "etag-1"


def test_html_extractor_ignores_script_and_style_content() -> None:
    fetch = HttpFetchResult(
        url="https://example.test/doc",
        status_code=200,
        body=b"<style>.x{}</style><p>Visible</p><noscript>hidden</noscript>",
        content_type="text/html; charset=utf-8",
        etag=None,
        last_modified=None,
        retrieved_at_monotonic=1.0,
    )

    text = HtmlDocumentTextExtractor().extract(fetch)

    assert "Visible" in text
    assert "hidden" not in text
