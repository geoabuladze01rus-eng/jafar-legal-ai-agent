from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from hashlib import sha256
from typing import Protocol

from .case_law_ingestion import CaseLawRecord


class SourceTrust(StrEnum):
    CANONICAL = "canonical"
    DISCOVERY = "discovery"


@dataclass(frozen=True, slots=True)
class CaseLawSourceItem:
    external_id: str
    citation: str
    court: str
    decided_on: date
    topic: str
    proposition: str
    source_url: str
    source_name: str
    authority_id: str
    trust: SourceTrust
    raw_fingerprint: str | None = None

    @property
    def candidate_fingerprint(self) -> str:
        if self.raw_fingerprint:
            return self.raw_fingerprint
        raw = "\n".join(
            (
                self.source_name.strip().casefold(),
                self.external_id.strip().casefold(),
                self.citation.strip().casefold(),
                self.decided_on.isoformat(),
                self.source_url.strip(),
            )
        )
        return sha256(raw.encode("utf-8")).hexdigest()


class CaseLawSourceAdapter(Protocol):
    name: str
    trust: SourceTrust

    def fetch_since(self, since: date | None = None) -> tuple[CaseLawSourceItem, ...]:
        """Return newly discovered source items.

        Implementations may read APIs, feeds, HTML or other approved source channels.
        The adapter must not silently promote discovery-only material to canonical status.
        """
        ...


class SupremeCourtSourceAdapter:
    """Contract for official Supreme Court of the Russian Federation source ingestion.

    Transport/parsing is injected by the caller so this module remains deterministic and
    testable. Items from this adapter are canonical candidates because provenance comes
    from an official source, but they still must pass the normal verification pipeline.
    """

    name = "supreme_court_rf"
    trust = SourceTrust.CANONICAL

    def __init__(self, fetcher: Protocol) -> None:
        self.fetcher = fetcher

    def fetch_since(self, since: date | None = None) -> tuple[CaseLawSourceItem, ...]:
        items = tuple(self.fetcher.fetch_since(since))
        return tuple(self._normalize(item) for item in items)

    def _normalize(self, item: CaseLawSourceItem) -> CaseLawSourceItem:
        return CaseLawSourceItem(
            external_id=item.external_id,
            citation=item.citation,
            court=item.court,
            decided_on=item.decided_on,
            topic=item.topic,
            proposition=item.proposition,
            source_url=item.source_url,
            source_name=self.name,
            authority_id=item.authority_id,
            trust=SourceTrust.CANONICAL,
            raw_fingerprint=item.raw_fingerprint,
        )


class SudactDiscoveryAdapter:
    """Discovery-only adapter for aggregated court-practice sources such as sudact.ru.

    Aggregator material may discover a candidate earlier or make it easier to search, but
    it must never become a verified authority solely because the aggregator returned it.
    """

    name = "sudact"
    trust = SourceTrust.DISCOVERY

    def __init__(self, fetcher: Protocol) -> None:
        self.fetcher = fetcher

    def fetch_since(self, since: date | None = None) -> tuple[CaseLawSourceItem, ...]:
        items = tuple(self.fetcher.fetch_since(since))
        return tuple(self._normalize(item) for item in items)

    def _normalize(self, item: CaseLawSourceItem) -> CaseLawSourceItem:
        return CaseLawSourceItem(
            external_id=item.external_id,
            citation=item.citation,
            court=item.court,
            decided_on=item.decided_on,
            topic=item.topic,
            proposition=item.proposition,
            source_url=item.source_url,
            source_name=self.name,
            authority_id=item.authority_id,
            trust=SourceTrust.DISCOVERY,
            raw_fingerprint=item.raw_fingerprint,
        )


@dataclass(frozen=True, slots=True)
class SourcePromotionDecision:
    item: CaseLawSourceItem
    may_enter_verification: bool
    may_supply_canonical_provenance: bool
    reasons: tuple[str, ...]


class CaseLawSourcePolicy:
    """Keep discovery and canonical provenance as separate trust domains."""

    @staticmethod
    def evaluate(item: CaseLawSourceItem) -> SourcePromotionDecision:
        if item.trust == SourceTrust.CANONICAL:
            return SourcePromotionDecision(
                item=item,
                may_enter_verification=True,
                may_supply_canonical_provenance=True,
                reasons=("Источник помечен как официальный/канонический кандидат.",),
            )
        return SourcePromotionDecision(
            item=item,
            may_enter_verification=True,
            may_supply_canonical_provenance=False,
            reasons=(
                "Агрегатор используется только для обнаружения; каноническая provenance должна быть подтверждена официальным источником.",
            ),
        )

    @staticmethod
    def to_case_law_record(item: CaseLawSourceItem, *, canonical_fingerprint: str) -> CaseLawRecord:
        if item.trust != SourceTrust.CANONICAL:
            raise ValueError("Discovery-only item cannot be converted to a canonical case-law record")
        if not canonical_fingerprint.strip():
            raise ValueError("canonical_fingerprint is required")
        return CaseLawRecord(
            record_id=f"case-law:{item.authority_id}",
            citation=item.citation,
            court=item.court,
            decided_on=item.decided_on,
            topic=item.topic,
            proposition=item.proposition,
            source_url=item.source_url,
            source_fingerprint=canonical_fingerprint,
            authority_id=item.authority_id,
        )
