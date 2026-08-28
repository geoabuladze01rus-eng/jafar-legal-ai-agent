from datetime import date

from jafar.authority_applicability import (
    ApplicabilityContext,
    ApplicabilityStatus,
    AuthorityApplicabilityEngine,
    AuthorityApplicabilityMetadata,
    AuthorityWeight,
)
from jafar.legal_authority_verification import (
    AuthorityCandidate,
    AuthorityStatus,
    AuthorityVerificationResult,
)


class FakeResolver:
    def __init__(self, metadata):
        self._metadata = metadata

    def metadata(self, result):
        return self._metadata


def verified() -> AuthorityVerificationResult:
    candidate = AuthorityCandidate(
        authority_id="a1",
        citation="ст. 75 УПК РФ",
        proposition="Требования к допустимости доказательств",
        source_url="https://canonical.example/a1",
    )
    return AuthorityVerificationResult(
        candidate=candidate,
        status=AuthorityStatus.VERIFIED,
        normalized_citation="ст. 75 УПК РФ",
        source_fingerprint="sha256:abc",
        reasons=("verified",),
    )


def test_verified_authority_can_be_applicable_only_after_context_checks() -> None:
    engine = AuthorityApplicabilityEngine(
        FakeResolver(
            AuthorityApplicabilityMetadata(
                authority_type="statute",
                weight=AuthorityWeight.BINDING,
                effective_from=date(2002, 7, 1),
                topics=("admissibility",),
                proceeding_types=("criminal",),
            )
        )
    )
    result = engine.assess(
        verified(),
        ApplicabilityContext(
            topic="admissibility",
            legal_question="Можно ли использовать доказательство?",
            relevant_date=date(2026, 8, 28),
            proceeding_type="criminal",
        ),
    )
    assert result.status == ApplicabilityStatus.APPLICABLE
    assert result.weight == AuthorityWeight.BINDING


def test_authority_outside_effective_time_is_not_applicable() -> None:
    engine = AuthorityApplicabilityEngine(
        FakeResolver(
            AuthorityApplicabilityMetadata(
                authority_type="statute",
                weight=AuthorityWeight.BINDING,
                effective_from=date(2027, 1, 1),
                topics=("admissibility",),
            )
        )
    )
    result = engine.assess(
        verified(),
        ApplicabilityContext(
            topic="admissibility",
            legal_question="Вопрос",
            relevant_date=date(2026, 8, 28),
        ),
    )
    assert result.status == ApplicabilityStatus.OUTSIDE_TIME


def test_superseded_authority_is_never_released_as_applicable() -> None:
    engine = AuthorityApplicabilityEngine(
        FakeResolver(
            AuthorityApplicabilityMetadata(
                authority_type="supreme_court_position",
                weight=AuthorityWeight.HIGH,
                topics=("admissibility",),
                superseded_by="Обзор ВС РФ от 01.08.2026",
            )
        )
    )
    result = engine.assess(
        verified(),
        ApplicabilityContext(topic="admissibility", legal_question="Вопрос"),
    )
    assert result.status == ApplicabilityStatus.SUPERSEDED
    assert result.superseded_by == "Обзор ВС РФ от 01.08.2026"


def test_negative_treatment_requires_human_review() -> None:
    engine = AuthorityApplicabilityEngine(
        FakeResolver(
            AuthorityApplicabilityMetadata(
                authority_type="case_law",
                weight=AuthorityWeight.PERSUASIVE,
                topics=("admissibility",),
                negative_treatment=("Позднейшая практика ограничила вывод.",),
            )
        )
    )
    result = engine.assess(
        verified(),
        ApplicabilityContext(topic="admissibility", legal_question="Вопрос"),
    )
    assert result.status == ApplicabilityStatus.REVIEW_REQUIRED


def test_verified_but_wrong_topic_is_not_applicable() -> None:
    engine = AuthorityApplicabilityEngine(
        FakeResolver(
            AuthorityApplicabilityMetadata(
                authority_type="statute",
                weight=AuthorityWeight.BINDING,
                topics=("detention",),
            )
        )
    )
    result = engine.assess(
        verified(),
        ApplicabilityContext(topic="admissibility", legal_question="Вопрос"),
    )
    assert result.status == ApplicabilityStatus.NOT_APPLICABLE


def test_unverified_authority_cannot_enter_applicability_release_gate() -> None:
    item = verified()
    unverified = AuthorityVerificationResult(
        candidate=item.candidate,
        status=AuthorityStatus.UNVERIFIED,
        normalized_citation=item.normalized_citation,
        source_fingerprint=None,
        reasons=("not verified",),
    )
    engine = AuthorityApplicabilityEngine(FakeResolver(None))
    result = engine.assess(
        unverified,
        ApplicabilityContext(topic="admissibility", legal_question="Вопрос"),
    )
    assert result.status == ApplicabilityStatus.REVIEW_REQUIRED
    assert not engine.release_ready((result,))
