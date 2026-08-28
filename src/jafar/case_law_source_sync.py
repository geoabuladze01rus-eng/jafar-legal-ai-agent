from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from .case_law_sources import CaseLawSourceAdapter, CaseLawSourceItem, SourceTrust


class SourceSyncStatus(StrEnum):
    CANONICAL_CANDIDATE = "canonical_candidate"
    DISCOVERY_ONLY = "discovery_only"
    MATCHED_TO_CANONICAL = "matched_to_canonical"
    DUPLICATE_SOURCE_ITEM = "duplicate_source_item"


@dataclass(frozen=True, slots=True)
class SourceSyncItem:
    item: CaseLawSourceItem
    status: SourceSyncStatus
    canonical_match_id: str | None = None
    requires_canonical_verification: bool = True


@dataclass(frozen=True, slots=True)
class SourceSyncReport:
    items: tuple[SourceSyncItem, ...]
    canonical_candidates: tuple[CaseLawSourceItem, ...]
    discovery_unmatched: tuple[CaseLawSourceItem, ...]
    requires_human_review: bool


class CaseLawSourceSyncEngine:
    """Merge multiple source feeds while preserving source-trust boundaries.

    Discovery-only records can be matched to canonical candidates for research convenience,
    but they never provide canonical provenance themselves.
    """

    def sync(
        self,
        adapters: tuple[CaseLawSourceAdapter, ...],
        *,
        since: date | None = None,
    ) -> SourceSyncReport:
        fetched: list[CaseLawSourceItem] = []
        for adapter in adapters:
            fetched.extend(adapter.fetch_since(since))

        unique: list[CaseLawSourceItem] = []
        seen: set[tuple[str, str, str]] = set()
        duplicates: list[CaseLawSourceItem] = []
        for item in fetched:
            key = (
                item.source_name.strip().casefold(),
                item.external_id.strip().casefold(),
                item.candidate_fingerprint,
            )
            if key in seen:
                duplicates.append(item)
                continue
            seen.add(key)
            unique.append(item)

        canonical = [item for item in unique if item.trust == SourceTrust.CANONICAL]
        discovery = [item for item in unique if item.trust == SourceTrust.DISCOVERY]

        canonical_index: dict[tuple[str, date, str], CaseLawSourceItem] = {}
        for item in canonical:
            canonical_index[self._match_key(item)] = item

        result: list[SourceSyncItem] = []
        for item in canonical:
            result.append(
                SourceSyncItem(
                    item=item,
                    status=SourceSyncStatus.CANONICAL_CANDIDATE,
                    canonical_match_id=item.external_id,
                    requires_canonical_verification=True,
                )
            )

        unmatched: list[CaseLawSourceItem] = []
        for item in discovery:
            match = canonical_index.get(self._match_key(item))
            if match is None:
                unmatched.append(item)
                result.append(
                    SourceSyncItem(
                        item=item,
                        status=SourceSyncStatus.DISCOVERY_ONLY,
                        canonical_match_id=None,
                        requires_canonical_verification=True,
                    )
                )
            else:
                result.append(
                    SourceSyncItem(
                        item=item,
                        status=SourceSyncStatus.MATCHED_TO_CANONICAL,
                        canonical_match_id=match.external_id,
                        requires_canonical_verification=True,
                    )
                )

        result.extend(
            SourceSyncItem(
                item=item,
                status=SourceSyncStatus.DUPLICATE_SOURCE_ITEM,
                requires_canonical_verification=True,
            )
            for item in duplicates
        )

        result.sort(
            key=lambda entry: (
                entry.item.decided_on,
                entry.item.citation.casefold(),
                entry.item.source_name.casefold(),
            )
        )
        return SourceSyncReport(
            items=tuple(result),
            canonical_candidates=tuple(canonical),
            discovery_unmatched=tuple(unmatched),
            requires_human_review=bool(unmatched),
        )

    @staticmethod
    def _match_key(item: CaseLawSourceItem) -> tuple[str, date, str]:
        return (
            CaseLawSourceSyncEngine._normalize_citation(item.citation),
            item.decided_on,
            item.court.strip().casefold(),
        )

    @staticmethod
    def _normalize_citation(value: str) -> str:
        return " ".join(value.casefold().replace("ё", "е").split())
