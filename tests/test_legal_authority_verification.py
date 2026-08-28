from jafar.legal_authority_verification import (
    AuthorityCandidate,
    AuthorityStatus,
    LegalAuthorityVerifier,
)


class FakeResolver:
    def __init__(self, citation: str, url: str | None, fingerprint: str | None) -> None:
        self.citation = citation
        self.url = url
        self.fingerprint = fingerprint

    def resolve(self, candidate: AuthorityCandidate) -> tuple[str, str | None, str | None]:
        return self.citation, self.url, self.fingerprint


def candidate(source_url: str | None = None) -> AuthorityCandidate:
    return AuthorityCandidate(
        authority_id="auth-1",
        citation="ст. 75 УПК РФ",
        proposition="Недопустимые доказательства не имеют юридической силы.",
        source_url=source_url,
    )


def test_verified_requires_canonical_url_and_fingerprint() -> None:
    verifier = LegalAuthorityVerifier(
        FakeResolver(
            "Статья 75 Уголовно-процессуального кодекса Российской Федерации",
            "https://official.example/75",
            "sha256:abc",
        )
    )
    result = verifier.verify(candidate())
    assert result.status == AuthorityStatus.VERIFIED
    assert result.source_fingerprint == "sha256:abc"
    assert result.to_outline_ref().verified is True


def test_missing_canonical_source_stays_unverified() -> None:
    verifier = LegalAuthorityVerifier(FakeResolver("", None, None))
    result = verifier.verify(candidate())
    assert result.status == AuthorityStatus.UNVERIFIED
    assert result.to_outline_ref().verified is False


def test_conflicting_url_does_not_promote_authority() -> None:
    verifier = LegalAuthorityVerifier(
        FakeResolver(
            "Статья 75 Уголовно-процессуального кодекса Российской Федерации",
            "https://official.example/75",
            "sha256:abc",
        )
    )
    result = verifier.verify(candidate("https://untrusted.example/75"))
    assert result.status == AuthorityStatus.CONFLICTING
    assert result.to_outline_ref().verified is False


def test_verified_refs_filters_non_verified_results() -> None:
    good = LegalAuthorityVerifier(
        FakeResolver("Статья 75 УПК РФ", "https://official.example/75", "sha256:1")
    ).verify(candidate())
    bad = LegalAuthorityVerifier(FakeResolver("", None, None)).verify(candidate())
    refs = LegalAuthorityVerifier.verified_refs((good, bad))
    assert len(refs) == 1
    assert refs[0].verified is True
