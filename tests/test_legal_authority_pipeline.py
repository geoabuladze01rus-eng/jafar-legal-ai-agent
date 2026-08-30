from jafar.court_outline import CourtOutline, OutlineKind
from jafar.legal_authority_pipeline import LegalAuthorityPipeline
from jafar.legal_authority_verification import AuthorityCandidate, LegalAuthorityVerifier


class FakeResolver:
    def __init__(self, ok: bool) -> None:
        self.ok = ok

    def resolve(self, candidate: AuthorityCandidate) -> tuple[str, str | None, str | None]:
        if not self.ok:
            return "", None, None
        return candidate.citation, "https://official.example/source", "sha256:verified"


def candidate() -> AuthorityCandidate:
    return AuthorityCandidate(
        authority_id="a1",
        citation="Проверяемая норма",
        proposition="Проверяемое правовое положение",
        source_url=None,
    )


def empty_outline(*, requires_source_verification: bool = False) -> CourtOutline:
    return CourtOutline(
        kind=OutlineKind.COURT_SPEECH,
        title="Позиция",
        sections=(),
        unverified_authorities=(),
        requires_source_verification=requires_source_verification,
    )


def test_pipeline_returns_only_verified_refs_for_outline() -> None:
    pipeline = LegalAuthorityPipeline(LegalAuthorityVerifier(FakeResolver(True)))
    reports = pipeline.verify_by_topic({"evidence": (candidate(),)})
    refs = pipeline.verified_refs_by_topic(reports)
    assert len(refs["evidence"]) == 1
    assert refs["evidence"][0].verified is True


def test_unresolved_authority_blocks_release_gate() -> None:
    pipeline = LegalAuthorityPipeline(LegalAuthorityVerifier(FakeResolver(False)))
    reports = pipeline.verify_by_topic({"evidence": (candidate(),)})
    assert pipeline.unresolved_citations(reports) == ("Проверяемая норма",)
    assert pipeline.outline_is_release_ready(empty_outline(), reports) is False


def test_outline_own_verification_flag_also_blocks_release() -> None:
    pipeline = LegalAuthorityPipeline(LegalAuthorityVerifier(FakeResolver(True)))
    reports = pipeline.verify_by_topic({"evidence": (candidate(),)})
    assert pipeline.outline_is_release_ready(
        empty_outline(requires_source_verification=True), reports
    ) is False
