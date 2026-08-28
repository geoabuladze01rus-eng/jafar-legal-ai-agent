from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from html.parser import HTMLParser
from typing import Protocol

from .case_law_transport import HttpFetchResult, ResilientHttpTransport


@dataclass(frozen=True, slots=True)
class CaseLawDocument:
    url: str
    text: str
    raw_fingerprint: str
    text_fingerprint: str
    content_type: str | None
    etag: str | None
    last_modified: str | None


class DocumentTextExtractor(Protocol):
    def extract(self, fetch: HttpFetchResult) -> str: ...


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._ignored = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._ignored += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._ignored:
            self._ignored -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored:
            value = " ".join(data.split())
            if value:
                self.parts.append(value)


class HtmlDocumentTextExtractor:
    """Conservative visible-text extractor for court-document HTML pages."""

    def extract(self, fetch: HttpFetchResult) -> str:
        charset = "utf-8"
        if fetch.content_type and "charset=" in fetch.content_type.casefold():
            charset = fetch.content_type.split("charset=", 1)[1].split(";", 1)[0].strip()
        html = fetch.body.decode(charset, errors="replace")
        parser = _VisibleTextParser()
        parser.feed(html)
        return "\n".join(parser.parts)


class CaseLawDocumentFetcher:
    """Fetch full court-document pages while preserving raw and normalized fingerprints."""

    def __init__(
        self,
        transport: ResilientHttpTransport,
        extractor: DocumentTextExtractor | None = None,
    ) -> None:
        self.transport = transport
        self.extractor = extractor or HtmlDocumentTextExtractor()

    def fetch(self, url: str) -> CaseLawDocument:
        response = self.transport.get(url)
        text = self.extractor.extract(response)
        normalized = self._normalize_text(text)
        return CaseLawDocument(
            url=response.url,
            text=normalized,
            raw_fingerprint=response.fingerprint,
            text_fingerprint=sha256(normalized.encode("utf-8")).hexdigest(),
            content_type=response.content_type,
            etag=response.etag,
            last_modified=response.last_modified,
        )

    @staticmethod
    def _normalize_text(value: str) -> str:
        lines = [" ".join(line.split()) for line in value.replace("\xa0", " ").splitlines()]
        return "\n".join(line for line in lines if line)
