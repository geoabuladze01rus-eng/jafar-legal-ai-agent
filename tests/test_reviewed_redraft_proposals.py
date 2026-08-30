from jafar.doctrine_case_impact import DoctrineImpactUrgency
from jafar.reviewed_redraft_proposals import (
    ProposalStyle,
    RedraftProposalCandidate,
    ReviewedRedraftProposalEngine,
    VerifiedRedraftAuthority,
)
from jafar.safe_fragment_redrafting import FragmentRedraftPacket


class StubGenerator:
    def generate(self, *, packet, authorities, max_options):
        authority = authorities[0]
        return (
            RedraftProposalCandidate(
                style=ProposalStyle.CONSERVATIVE,
                proposed_text="Уточнённый довод с учётом актуальной позиции суда.",
                rationale="Сужает формулировку до подтверждённого правила.",
                authority_ids=(authority.authority_id,),
                rule_ids=authority.rule_ids,
            ),
            RedraftProposalCandidate(
                style=ProposalStyle.BALANCED,
                proposed_text="Альтернативная редакция довода с явной оговоркой.",
                rationale="Сохраняет фактическую основу и обновляет правовую опору.",
                authority_ids=(authority.authority_id,),
                rule_ids=authority.rule_ids,
            ),
            RedraftProposalCandidate(
                style=ProposalStyle.ASSERTIVE,
                proposed_text="Более категоричная, но всё ещё проверяемая редакция довода.",
                rationale="Использует только подтверждённые authority и rule ids.",
                authority_ids=(authority.authority_id,),
                rule_ids=authority.rule_ids,
            ),
        )


def packet(source_refs=("evidence:1",)):
    return FragmentRedraftPacket(
        fragment_id="complaint:p3",
        work_product_id="complaint:1",
        original_text="Старый довод.",
        source_refs=source_refs,
        authority_ids=("auth-old",),
        rule_ids=("rule-current",),
        urgency=DoctrineImpactUrgency.CRITICAL,
        stale=True,
        risk_reasons=("Правило заменено.",),
        options=(),
        mandatory_checks=("Проверить authority",),
    )


def authority(**overrides):
    data = {
        "authority_id": "auth-current",
        "citation": "Определение Верховного Суда РФ",
        "proposition": "Актуальная проверенная позиция.",
        "source_url": "https://vsrf.ru/example",
        "rule_ids": ("rule-current",),
    }
    data.update(overrides)
    return VerifiedRedraftAuthority(**data)


def test_generates_up_to_three_reviewed_options_and_never_auto_applies():
    report = ReviewedRedraftProposalEngine(StubGenerator()).propose(
        packet=packet(), authorities=(authority(),), max_options=3
    )

    assert len(report.proposals) == 3
    assert report.may_replace_fragment is False
    assert all(item.may_auto_apply is False for item in report.proposals)
    assert all(item.requires_lawyer_approval for item in report.proposals)
    assert all(item.diff_lines for item in report.proposals)
    assert ReviewedRedraftProposalEngine.release_ready(report) is True


def test_unverified_authority_blocks_generation():
    report = ReviewedRedraftProposalEngine(StubGenerator()).propose(
        packet=packet(), authorities=(authority(verified=False),)
    )

    assert report.proposals == ()
    assert any("not verified" in reason for reason in report.blocked_reasons)
    assert report.may_replace_fragment is False


def test_noncurrent_authority_blocks_generation():
    report = ReviewedRedraftProposalEngine(StubGenerator()).propose(
        packet=packet(), authorities=(authority(current=False),)
    )

    assert report.proposals == ()
    assert any("not current" in reason for reason in report.blocked_reasons)


def test_missing_source_refs_prevents_review_release():
    report = ReviewedRedraftProposalEngine(StubGenerator()).propose(
        packet=packet(source_refs=()), authorities=(authority(),), max_options=1
    )

    assert len(report.proposals) == 1
    assert report.proposals[0].passed_source_ref_gate is False
    assert ReviewedRedraftProposalEngine.release_ready(report) is False


def test_max_options_is_bounded():
    engine = ReviewedRedraftProposalEngine(StubGenerator())
    try:
        engine.propose(packet=packet(), authorities=(authority(),), max_options=4)
    except ValueError as exc:
        assert "between 1 and 3" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
