from datetime import date

from jafar.authority_applicability import (
    ApplicabilityStatus,
    AuthorityApplicabilityResult,
    AuthorityWeight,
)
from jafar.case_law_ingestion import (
    ActiveCaseProfile,
    CaseImpactLevel,
    CaseLawIngestionEngine,
    CaseLawRecord,
    CaseLawRepository,
    IngestionStatus,
)
from jafar.legal_authority_verification import (
    AuthorityCandidate,
    AuthorityStatus,
    AuthorityVerificationResult,
)
from jafar.precedent_freshness import (
    FreshnessStatus,
    PrecedentFreshnessItem,
    PrecedentFreshnessReport,
    PrecedentRecord,
)


def _verification(status: AuthorityStatus = AuthorityStatus.VERIFIED) -> AuthorityVerificationResult:
    candidate = AuthorityCandidate(
        authority_id="sc-2026-1",
        citation="Позиция ВС РФ от 01.08.2026",
        proposition="Проверка допустимости доказательства",
        source_url="https://example.test/sc-2026-1",
    )
    return AuthorityVerificationResult(
        candidate=candidate,
        status=status,
        normalized_citation=candidate.citation,
        source_fingerprint="fp-authority" if status == AuthorityStatus.VERIFIED else None,
        reasons=("verified",),
    )


def _applicability(
    verification: AuthorityVerificationResult,
    status: ApplicabilityStatus = ApplicabilityStatus.APPLICABLE,
) -> AuthorityApplicabilityResult:
    return AuthorityApplicabilityResult(
        verification=verification,
        status=status,
        weight=AuthorityWeight.HIGH,
        reasons=("applicable",),
    )


def _record() -> CaseLawRecord:
    return CaseLawRecord(
        record_id="record-1",
        citation="Позиция ВС РФ от 01.08.2026",
        court="Верховный Суд РФ",
        decided_on=date(2026, 8, 1),
        topic="допустимость доказательств",
        proposition="Проверка допустимости доказательства",
        source_url="https://example.test/sc-2026-1",
        source_fingerprint="fp-authority",
        authority_id="sc-2026-1",
    )


def _freshness(status: FreshnessStatus = FreshnessStatus.CURRENT) -> PrecedentFreshnessReport:
    precedent = PrecedentRecord(
        authority_id="sc-2026-1",
        citation="Позиция ВС РФ от 01.08.2026",
        topic="допустимость доказательств",
        proposition="Проверка допустимости доказательства",
        decided_on=date(2026, 8, 1),
        weight=AuthorityWeight.HIGH,
        authority_type="supreme_court",
        source_url="https://example.test/sc-2026-1",
        source_fingerprint="fp-authority",
    )
    item = PrecedentFreshnessItem(
        precedent=precedent,
        status=status,
        freshness_rank=500,
        reasons=("freshness",),
        later_relations=(),
    )
    return PrecedentFreshnessReport(
        topic=precedent.topic,
        chronology=(precedent,),
        items=(item,),
        conflicts=(),
        requires_human_review=status == FreshnessStatus.CONFLICTING,
    )


def test_ingests_verified_applicable_case_law_and_flags_matching_active_case() -> None:
    verification = _verification()
    engine = CaseLawIngestionEngine(repository=CaseLawRepository())
    result = engine.ingest(
        record=_record(),
        verification=verification,
        applicability=_applicability(verification),
        freshness=_freshness(),
        active_cases=(
            ActiveCaseProfile(
                case_id="case-pavlik",
                title="Павлик",
                topics=("допустимость доказательств", "таможенные платежи"),
            ),
        ),
    )

    assert result.ingestion_status == IngestionStatus.NEW
    assert result.case_impacts[0].case_id == "case-pavlik"
    assert result.case_impacts[0].impact_level == CaseImpactLevel.HIGH
    assert result.case_impacts[0].requires_lawyer_review is True


def test_deduplicates_same_case_law_by_requisites_and_fingerprint() -> None:
    verification = _verification()
    repository = CaseLawRepository()
    engine = CaseLawIngestionEngine(repository=repository)
    kwargs = {
        "record": _record(),
        "verification": verification,
        "applicability": _applicability(verification),
    }

    first = engine.ingest(**kwargs)
    second = engine.ingest(**kwargs)

    assert first.ingestion_status == IngestionStatus.NEW
    assert second.ingestion_status == IngestionStatus.DUPLICATE
    assert len(repository.records()) == 1


def test_blocks_unverified_case_law_from_repository_and_case_impact() -> None:
    verification = _verification(AuthorityStatus.UNVERIFIED)
    repository = CaseLawRepository()
    result = CaseLawIngestionEngine(repository=repository).ingest(
        record=_record(),
        verification=verification,
        applicability=_applicability(verification, ApplicabilityStatus.REVIEW_REQUIRED),
        active_cases=(
            ActiveCaseProfile(
                case_id="case-1",
                title="Case",
                topics=("допустимость доказательств",),
            ),
        ),
    )

    assert result.ingestion_status == IngestionStatus.BLOCKED
    assert result.case_impacts == ()
    assert repository.records() == ()
    assert result.requires_human_review is True


def test_existing_authority_in_case_becomes_critical_recheck() -> None:
    verification = _verification()
    result = CaseLawIngestionEngine(repository=CaseLawRepository()).ingest(
        record=_record(),
        verification=verification,
        applicability=_applicability(verification),
        freshness=_freshness(FreshnessStatus.OLDER_BUT_CONTROLLING),
        active_cases=(
            ActiveCaseProfile(
                case_id="case-1",
                title="Case",
                topics=("допустимость доказательств",),
                authority_ids_in_use=("sc-2026-1",),
            ),
        ),
    )

    assert result.case_impacts[0].impact_level == CaseImpactLevel.CRITICAL
    assert "повторной проверки" in " ".join(result.case_impacts[0].reasons)


def test_unrelated_active_case_is_not_flagged() -> None:
    verification = _verification()
    result = CaseLawIngestionEngine(repository=CaseLawRepository()).ingest(
        record=_record(),
        verification=verification,
        applicability=_applicability(verification),
        active_cases=(
            ActiveCaseProfile(
                case_id="case-2",
                title="Other",
                topics=("налоговый спор",),
            ),
        ),
    )

    assert result.case_impacts == ()
