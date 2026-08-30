from datetime import date

from jafar.authority_applicability import (
    ApplicabilityContext,
    AuthorityApplicabilityEngine,
    AuthorityApplicabilityMetadata,
    AuthorityWeight,
)
from jafar.authority_applicability_pipeline import AuthorityApplicabilityPipeline
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


def verification() -> AuthorityVerificationResult:
    candidate = AuthorityCandidate(
        authority_id="a1",
        citation="ст. 75 УПК РФ",
        proposition="Допустимость доказательств",
        source_url="https://canonical.example/a1",
    )
    return AuthorityVerificationResult(
        candidate=candidate,
        status=AuthorityStatus.VERIFIED,
        normalized_citation="ст. 75 УПК РФ",
        source_fingerprint="sha256:abc",
        reasons=("verified",),
    )


def test_pipeline_promotes_only_applicable_authority() -> None:
    pipeline = AuthorityApplicabilityPipeline(
        AuthorityApplicabilityEngine(
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
    )
    result = pipeline.run(
        ((
            "admissibility",
            verification(),
            ApplicabilityContext(
                topic="admissibility",
                legal_question="Вопрос допустимости",
                relevant_date=date(2026, 8, 28),
                proceeding_type="criminal",
            ),
        ),)
    )
    assert result.release_ready
    assert result.blocked_citations == ()
    assert result.applicable_refs_by_topic["admissibility"][0].verified is True


def test_pipeline_blocks_superseded_authority_from_outline_inputs() -> None:
    pipeline = AuthorityApplicabilityPipeline(
        AuthorityApplicabilityEngine(
            FakeResolver(
                AuthorityApplicabilityMetadata(
                    authority_type="case_law",
                    weight=AuthorityWeight.HIGH,
                    topics=("admissibility",),
                    superseded_by="Позднейшая позиция ВС РФ",
                )
            )
        )
    )
    result = pipeline.run(
        ((
            "admissibility",
            verification(),
            ApplicabilityContext(topic="admissibility", legal_question="Вопрос"),
        ),)
    )
    assert not result.release_ready
    assert result.applicable_refs_by_topic == {}
    assert result.blocked_citations == ("ст. 75 УПК РФ",)
