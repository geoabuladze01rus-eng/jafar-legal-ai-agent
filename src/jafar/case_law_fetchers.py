from __future__ import annotations

from datetime import date
from urllib.parse import urlencode

from .case_law_parsers import LinkBasedCaseLawParser, ParsedCaseLawPage
from .case_law_sources import CaseLawSourceItem, SourceTrust
from .case_law_transport import ResilientHttpTransport


class SupremeCourtHttpFetcher:
    """Fetch official Supreme Court RF case-law pages from vsrf.ru.

    The official site's electronic reference contains texts of Supreme Court judicial acts.
    Parsing remains conservative: discovery of links is separated from legal enrichment.
    """

    BASE_URL = "https://www.vsrf.ru/lk/practice/acts"

    def __init__(self, transport: ResilientHttpTransport | None = None) -> None:
        self.transport = transport or ResilientHttpTransport(min_interval_seconds=0.75)
        self.parser = LinkBasedCaseLawParser(
            source_name="supreme_court_rf",
            trust=SourceTrust.CANONICAL,
            court="Верховный Суд Российской Федерации",
        )
        self.last_page: ParsedCaseLawPage | None = None

    def fetch_since(self, since: date | None = None) -> tuple[CaseLawSourceItem, ...]:
        params: dict[str, str] = {}
        if since is not None:
            # Kept as a transparent query hint. Site-side filtering may evolve; the raw
            # resolved URL and body fingerprint remain stored for audit.
            params["date_from"] = since.isoformat()
        url = self.BASE_URL if not params else f"{self.BASE_URL}?{urlencode(params)}"
        fetched = self.transport.get(url)
        self.last_page = self.parser.parse(fetched)
        return tuple(
            item
            for item in self.last_page.items
            if since is None or item.decided_on == date.min or item.decided_on >= since
        )


class SudactHttpFetcher:
    """Discovery-only fetcher for Sudact public result pages."""

    BASE_URL = "https://sudact.ru/vsrf/"

    def __init__(self, transport: ResilientHttpTransport | None = None) -> None:
        self.transport = transport or ResilientHttpTransport(min_interval_seconds=1.0)
        self.parser = LinkBasedCaseLawParser(
            source_name="sudact",
            trust=SourceTrust.DISCOVERY,
            court="Верховный Суд Российской Федерации",
        )
        self.last_page: ParsedCaseLawPage | None = None

    def fetch_since(self, since: date | None = None) -> tuple[CaseLawSourceItem, ...]:
        fetched = self.transport.get(self.BASE_URL)
        self.last_page = self.parser.parse(fetched)
        return tuple(
            item
            for item in self.last_page.items
            if since is None or item.decided_on == date.min or item.decided_on >= since
        )
