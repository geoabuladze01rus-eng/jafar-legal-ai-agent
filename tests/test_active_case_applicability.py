from datetime import date

from jafar.active_case_applicability import ActiveCaseApplicabilityPipeline
from jafar.authority_applicability import (
    ApplicabilityStatus,
    AuthorityApplicabilityEngine,
    AuthorityApplicabilityMetadata,
    AuthorityWeight,
)
from jafar.case_law_ingestion import ActiveCaseProfile
from jafar.legal_authority_verification import (
    AuthorityCandidate,
    AuthorityStatus,
    AuthorityVerificationResult,
)


class Resolver:
    def metadata(self, result: AuthorityVerificationResult) -> AuthorityApplicabilityMetadata:
        return AuthorityApplicabilityMetadata(
            authority_type="supreme_court",
            weight=AuthorityWeight.HIGH,
            effective_from=date(2026, 8, 1),
            topics=("меры пресечения",),
            proceeding_types=("уголовное",),
        )


def verification() -> AuthorityVerificationResult:
    candidate = AuthorityCandidate(
        authority_id="vs-2026-8",
        citation="Определение Верховного Суда РФ",
        proposition="Правовая позиция по мере пресечения",
        source_url="https://www.vsrf.ru/example",
    )
    return AuthorityVerificationResult(
        candidate=candidate,
        status=AuthorityStatus.VERIFIED,
        normalized_citation=candidate.citation,
        source_fingerprint="fp",
        reasons=("verified",),
    )


def test_assesses_same_authority_per_case_date_and_proceeding() -> None:
    pipeline = ActiveCaseApplicabilityPipeline(
        applicability_engine=AuthorityApplicabilityEngine(Resolver())
    )
    report = pipeline.analyze(
        verification=verification(),
        topic="меры пресечения",
        active_cases=(
            ActiveCaseProfile(
                case_id="new-case",
                title="Новое дело",
                topics=("меры пресечения",),
                proceeding_type="уголовное",
                relevant_date=date(2026, 8, 20),
            ),
            ActiveCaseProfile(
                case_id="old-case",
                title="Старое дело",
                topics=("меры пресечения",),
                proceeding_type="уголовное",
                relevant_date=date(2026, 7, 20),
            ),
            ActiveCaseProfile(
                case_id="civil-case",
                title="Гражданское дело",
                topics=("меры пресечения",),
                proceeding_type="гражданское",
                relevant_date=date(2026, 8, 20),
            ),
        ),
    )

    by_case = {item.case_id: item for item in report.cases}
    assert by_case["new-case"].applicability.status == ApplicabilityStatus.APPLICABLE
    assert by_case["old-case"].applicability.status == ApplicabilityStatus.OUTSIDE_TIME
    assert by_case["civil-case"].applicability.status == ApplicabilityStatus.NOT_APPLICABLE
    assert report.requires_lawyer_review is True


def test_unrelated_case_is_not_in_report() -> None:
    pipeline = ActiveCaseApplicabilityPipeline(
        applicability_engine=AuthorityApplicabilityEngine(Resolver())
    )
    report = pipeline.analyze(
        verification=verification(),
        topic="меры пресечения",
        active_cases=(
            ActiveCaseProfile(
                case_id="tax",
                title="Налоговое дело",
                topics=("налог",),
            ),
        ),
    )
    assert report.cases == ()
