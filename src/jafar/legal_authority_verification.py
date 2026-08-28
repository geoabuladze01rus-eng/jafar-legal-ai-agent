from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from .court_outline import LegalAuthorityRef


class AuthorityStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    CONFLICTING = "conflicting"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class AuthorityCandidate:
    authority_id: str
    citation: str
    proposition: str
    source_url: str | None
    source_name: str | None = None
    effective_date: str | None = None
    retrieved_at: str | None = None


@dataclass(frozen=True, slots=True)
class AuthorityVerificationResult:
    candidate: AuthorityCandidate
    status: AuthorityStatus
    normalized_citation: str
    source_fingerprint: str | None
    reasons: tuple[str, ...]

    def to_outline_ref(self) -> LegalAuthorityRef:
        return LegalAuthorityRef(
            citation=self.normalized_citation,
            proposition=self.candidate.proposition,
            verified=self.status == AuthorityStatus.VERIFIED,
            source_url=self.candidate.source_url,
        )


class AuthorityResolver(Protocol):
    def resolve(self, candidate: AuthorityCandidate) -> tuple[str, str | None, str | None]:
        """Return canonical citation, canonical source URL, and stable source fingerprint."""
        ...


class LegalAuthorityVerifier:
    """Verify legal authorities only against an external canonical resolver.

    This class never guesses statutes or court holdings. If a canonical source cannot be
    resolved, the authority remains unverified and must not be promoted to a verified ref.
    """

    def __init__(self, resolver: AuthorityResolver) -> None:
        self.resolver = resolver

    def verify(self, candidate: AuthorityCandidate) -> AuthorityVerificationResult:
        canonical_citation, canonical_url, source_fingerprint = self.resolver.resolve(candidate)
        reasons: list[str] = []

        if not canonical_citation or not canonical_url or not source_fingerprint:
            reasons.append("Не удалось подтвердить реквизиты по каноническому источнику.")
            return AuthorityVerificationResult(
                candidate=candidate,
                status=AuthorityStatus.UNVERIFIED,
                normalized_citation=candidate.citation,
                source_fingerprint=None,
                reasons=tuple(reasons),
            )

        if candidate.source_url and candidate.source_url != canonical_url:
            reasons.append("Указанный URL не совпадает с каноническим источником.")
            return AuthorityVerificationResult(
                candidate=candidate,
                status=AuthorityStatus.CONFLICTING,
                normalized_citation=canonical_citation,
                source_fingerprint=source_fingerprint,
                reasons=tuple(reasons),
            )

        reasons.append("Реквизиты подтверждены каноническим источником.")
        return AuthorityVerificationResult(
            candidate=AuthorityCandidate(
                authority_id=candidate.authority_id,
                citation=candidate.citation,
                proposition=candidate.proposition,
                source_url=canonical_url,
                source_name=candidate.source_name,
                effective_date=candidate.effective_date,
                retrieved_at=candidate.retrieved_at,
            ),
            status=AuthorityStatus.VERIFIED,
            normalized_citation=canonical_citation,
            source_fingerprint=source_fingerprint,
            reasons=tuple(reasons),
        )

    def verify_many(
        self,
        candidates: tuple[AuthorityCandidate, ...],
    ) -> tuple[AuthorityVerificationResult, ...]:
        return tuple(self.verify(candidate) for candidate in candidates)

    @staticmethod
    def verified_refs(
        results: tuple[AuthorityVerificationResult, ...],
    ) -> tuple[LegalAuthorityRef, ...]:
        return tuple(
            result.to_outline_ref()
            for result in results
            if result.status == AuthorityStatus.VERIFIED
        )
