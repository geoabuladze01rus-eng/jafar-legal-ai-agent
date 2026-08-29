from datetime import UTC, datetime

import pytest

from jafar.doctrine_case_impact import WorkProductKind
from jafar.lawyer_approval_patch import LawyerApprovalPatchEngine
from jafar.reviewed_redraft_proposals import ProposalStyle, ReviewedRedraftProposal
from jafar.work_product_dependency_graph import FragmentKind, WorkProductFragment


def proposal(**overrides):
    data = dict(
        fragment_id="complaint:p3",
        original_text="Старый довод.",
        proposed_text="Новый проверенный довод.",
        style=ProposalStyle.BALANCED,
        rationale="Актуализация правовой опоры.",
        authority_ids=("auth:new",),
        rule_ids=("rule:new",),
        diff_lines=("- Старый довод.", "+ Новый проверенный довод."),
        passed_authority_gate=True,
        passed_source_ref_gate=True,
    )
    data.update(overrides)
    return ReviewedRedraftProposal(**data)


def fragment(text="Старый довод."):
    return WorkProductFragment(
        fragment_id="complaint:p3",
        work_product_id="complaint:1",
        work_product_kind=WorkProductKind.COMPLAINT,
        fragment_kind=FragmentKind.ARGUMENT,
        ordinal=3,
        text=text,
        topic="допустимость доказательств",
        authority_ids=("auth:old",),
        rule_ids=("rule:old",),
        source_refs=("evidence:1",),
    )


def test_approval_is_immutable_and_bound_to_proposal_hash():
    engine = LawyerApprovalPatchEngine()
    item = proposal()
    approval = engine.approve(
        proposal=item,
        approved_by="lawyer-1",
        approved_at=datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
    )
    assert approval.immutable is True
    assert approval.proposal_hash == engine.proposal_hash(item)
    assert approval.fragment_id == item.fragment_id


def test_patch_requires_exact_approved_proposal_and_current_fragment_text():
    engine = LawyerApprovalPatchEngine()
    item = proposal()
    approval = engine.approve(proposal=item, approved_by="lawyer-1")
    patch = engine.prepare_patch(fragment=fragment(), proposal=item, approval=approval)
    assert patch.ready_for_explicit_apply is True
    assert patch.may_auto_apply is False
    assert engine.may_apply(patch) is True


def test_fragment_change_after_proposal_blocks_patch():
    engine = LawyerApprovalPatchEngine()
    item = proposal()
    approval = engine.approve(proposal=item, approved_by="lawyer-1")
    with pytest.raises(ValueError, match="changed since proposal generation"):
        engine.prepare_patch(fragment=fragment("Текст уже изменён."), proposal=item, approval=approval)


def test_tampered_proposal_is_rejected_after_approval():
    engine = LawyerApprovalPatchEngine()
    item = proposal()
    approval = engine.approve(proposal=item, approved_by="lawyer-1")
    altered = proposal(proposed_text="Подменённая редакция.")
    with pytest.raises(ValueError, match="does not bind"):
        engine.prepare_patch(fragment=fragment(), proposal=altered, approval=approval)


def test_unpassed_proposal_cannot_be_approved():
    engine = LawyerApprovalPatchEngine()
    with pytest.raises(ValueError, match="required review gates"):
        engine.approve(
            proposal=proposal(passed_authority_gate=False),
            approved_by="lawyer-1",
        )


def test_reviewer_identity_is_required():
    engine = LawyerApprovalPatchEngine()
    with pytest.raises(ValueError, match="approved_by"):
        engine.approve(proposal=proposal(), approved_by="   ")
