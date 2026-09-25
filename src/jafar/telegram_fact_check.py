from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, Sequence
from urllib.parse import urlparse

from .telegram_publication import FactCheckResult, FactCheckStatus, SourceEvidence


OFFICIAL_SOURCE_DOMAINS: tuple[tuple[str, int], ...] = (
    ("publication.pravo.gov.ru", 1),
    ("vsrf.ru", 2),
    ("ksrf.ru", 3),
    ("sudrf.ru", 4),
    ("genproc.gov.ru", 5),
    ("sledcom.ru", 5),
    ("мвд.рф", 5),
    ("consultant.ru", 6),
    ("garant.ru", 6),
)


@dataclass(frozen=True, slots=True)
class ClaimEvidence:
    claim: str
    sources: tuple[SourceEvidence, ...]

    @property
    def has_legal_authority(self) -> bool:
        return any(source.verified and source.authority_rank <= 6 for source in self.sources)


class LegalFactCheckProvider(Protocol):
    def verify_claim(self, claim: str) -> Sequence[SourceEvidence]: ...


@dataclass(slots=True)
class TelegramLegalFactChecker:
    """Fail-closed verification for legal claims used in public channel content.

    A professional-media source may support discovery, but it cannot by itself
    verify a legal proposition. At least one verified source from authority tiers
    1-6 is required for every legal claim.
    """

    provider: LegalFactCheckProvider

    def check(self, claims: Sequence[str]) -> FactCheckResult:
        normalized = tuple(claim.strip() for claim in claims if claim.strip())
        if not normalized:
            return FactCheckResult(
                status=FactCheckStatus.UNVERIFIED,
                checked_at=datetime.now(timezone.utc),
                notes="No legal claims were supplied for verification.",
            )

        findings: list[ClaimEvidence] = []
        all_sources: list[SourceEvidence] = []
        try:
            for claim in normalized:
                sources = tuple(self.provider.verify_claim(claim))
                findings.append(ClaimEvidence(claim=claim, sources=sources))
                all_sources.extend(sources)
        except Exception as exc:
            return FactCheckResult(
                status=FactCheckStatus.FAILED,
                checked_at=datetime.now(timezone.utc),
                notes=f"Fact-check provider failed: {type(exc).__name__}",
            )

        missing = [finding.claim for finding in findings if not finding.has_legal_authority]
        status = FactCheckStatus.UNVERIFIED if missing else FactCheckStatus.VERIFIED
        notes = None
        if missing:
            notes = "Unverified legal claims: " + " | ".join(missing)

        return FactCheckResult(
            status=status,
            sources=_deduplicate_sources(all_sources),
            checked_at=datetime.now(timezone.utc),
            notes=notes,
        )


def authority_rank_for_url(url: str) -> int:
    host = (urlparse(url).hostname or "").lower()
    for domain, rank in OFFICIAL_SOURCE_DOMAINS:
        if host == domain or host.endswith("." + domain):
            return rank
    return 7


def source_evidence(*, title: str, url: str, verified: bool) -> SourceEvidence:
    return SourceEvidence(
        title=title,
        url=url,
        authority_rank=authority_rank_for_url(url),
        verified=verified,
    )


def _deduplicate_sources(sources: Sequence[SourceEvidence]) -> list[SourceEvidence]:
    result: list[SourceEvidence] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        key = (source.title, source.url)
        if key in seen:
            continue
        seen.add(key)
        result.append(source)
    return result
