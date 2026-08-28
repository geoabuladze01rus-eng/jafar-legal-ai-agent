from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from html.parser import HTMLParser
import re
from typing import Protocol

from .case_law_sources import CaseLawSourceItem, SourceTrust
from .case_law_transport import HttpFetchResult


@dataclass(frozen=True, slots=True)
class RawSourceProvenance:
    requested_url: str
    resolved_url: str
    body_fingerprint: str
    content_type: str | None
    etag: str | None
    last_modified: str | None


@dataclass(frozen=True, slots=True)
class ParsedCaseLawPage:
    items: tuple[CaseLawSourceItem, ...]
    provenance: RawSourceProvenance


class CaseLawPageParser(Protocol):
    def parse(self, fetched: HttpFetchResult) -> ParsedCaseLawPage: ...


class _LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a":
            return
        values = dict(attrs)
        self._href = values.get("href")
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self._href is None:
            return
        text = " ".join("".join(self._text).split())
        self.links.append((self._href, text))
        self._href = None
        self._text = []


class LinkBasedCaseLawParser:
    """Conservative HTML discovery parser.

    This parser extracts candidate links only. Legal topics/propositions must be enriched by
    a later deterministic extractor or lawyer-reviewed model stage before ingestion.
    """

    _RUSSIAN_MONTHS = {
        "января": 1,
        "февраля": 2,
        "марта": 3,
        "апреля": 4,
        "мая": 5,
        "июня": 6,
        "июля": 7,
        "августа": 8,
        "сентября": 9,
        "октября": 10,
        "ноября": 11,
        "декабря": 12,
    }

    def __init__(self, *, source_name: str, trust: SourceTrust, court: str) -> None:
        self.source_name = source_name
        self.trust = trust
        self.court = court

    def parse(self, fetched: HttpFetchResult) -> ParsedCaseLawPage:
        text = fetched.body.decode("utf-8", errors="replace")
        collector = _LinkCollector()
        collector.feed(text)
        items: list[CaseLawSourceItem] = []
        for href, label in collector.links:
            if not self._looks_like_case_law(label):
                continue
            external_id = sha256(f"{href}\n{label}".encode("utf-8")).hexdigest()[:24]
            items.append(
                CaseLawSourceItem(
                    external_id=external_id,
                    citation=label,
                    court=self.court,
                    decided_on=self._extract_date(label) or date.min,
                    topic="unclassified",
                    proposition="",
                    source_url=self._absolute_url(fetched.url, href),
                    source_name=self.source_name,
                    authority_id=f"source:{external_id}",
                    trust=self.trust,
                    raw_fingerprint=fetched.fingerprint,
                )
            )
        return ParsedCaseLawPage(
            items=tuple(items),
            provenance=RawSourceProvenance(
                requested_url=fetched.requested_url or fetched.url,
                resolved_url=fetched.url,
                body_fingerprint=fetched.fingerprint,
                content_type=fetched.content_type,
                etag=fetched.etag,
                last_modified=fetched.last_modified,
            ),
        )

    @staticmethod
    def _looks_like_case_law(label: str) -> bool:
        value = label.casefold()
        tokens = ("определение", "постановление", "решение", "обзор судебной практики")
        return any(token in value for token in tokens)

    @classmethod
    def _extract_date(cls, label: str) -> date | None:
        numeric = re.search(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})\b", label)
        if numeric:
            day, month, year = map(int, numeric.groups())
            return cls._safe_date(year, month, day)

        months = "|".join(cls._RUSSIAN_MONTHS)
        words = re.search(
            rf"\b(\d{{1,2}})\s+({months})\s+(\d{{4}})(?:\s*г(?:ода|\.)?)?\b",
            label.casefold(),
        )
        if not words:
            return None
        day = int(words.group(1))
        month = cls._RUSSIAN_MONTHS[words.group(2)]
        year = int(words.group(3))
        return cls._safe_date(year, month, day)

    @staticmethod
    def _safe_date(year: int, month: int, day: int) -> date | None:
        try:
            return date(year, month, day)
        except ValueError:
            return None

    @staticmethod
    def _absolute_url(base: str, href: str) -> str:
        from urllib.parse import urljoin

        return urljoin(base, href)
