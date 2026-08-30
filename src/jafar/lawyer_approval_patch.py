from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from .reviewed_redraft_proposals import ReviewedRedraftProposal
from .work_product_dependency_graph import WorkProductFragment


@dataclass(frozen=True, slots=True)
class LawyerApprovalRecord:
    approval_id: str
    fragment_id: str
    proposal_hash: str
    approved_text_hash: str
    authority_ids: tuple[str, ...]
    rule_ids: tuple[str, ...]
    approved_by: str
    approved_at: datetime
    comment: str = ""
    immutable: bool = True


@dataclass(frozen=True, slots=True)
class ControlledFragmentPatch:
    patch_id: str
    fragment_id: str
    work_product_id: str
    original_text_hash: str
    replacement_text: str
    replacement_text_hash: str
    approval_id: str
    proposal_hash: str
    authority_ids: tuple[str, ...]
    rule_ids: tuple[str, ...]
    ready_for_explicit_apply: bool
    may_auto_apply: bool = False


class LawyerApprovalPatchEngine:
    """Create immutable lawyer approvals and controlled fragment patches.

    Approval and patch creation are deliberately separate from mutation of a document.
    A patch may become ready for explicit application only when the proposal matches the
    current fragment text and the supplied approval cryptographically binds that proposal.
    """

    def approve(
        self,
        *,
        proposal: ReviewedRedraftProposal,
        approved_by: str,
        comment: str = "",
        approved_at: datetime | None = None,
    ) -> LawyerApprovalRecord:
        reviewer = approved_by.strip()
        if not reviewer:
            raise ValueError("approved_by is required")
        if proposal.may_auto_apply:
            raise ValueError("Unsafe proposal: may_auto_apply must remain false")
        if not proposal.passed_authority_gate or not proposal.passed_source_ref_gate:
            raise ValueError("Proposal has not passed required review gates")

        timestamp = approved_at or datetime.now(UTC)
        if timestamp.tzinfo is None:
            raise ValueError("approved_at must be timezone-aware")
        proposal_hash = self.proposal_hash(proposal)
        approved_text_hash = self._hash(proposal.proposed_text)
        approval_id = f"approval:{proposal.fragment_id}:{proposal_hash[:16]}"
        return LawyerApprovalRecord(
            approval_id=approval_id,
            fragment_id=proposal.fragment_id,
            proposal_hash=proposal_hash,
            approved_text_hash=approved_text_hash,
            authority_ids=proposal.authority_ids,
            rule_ids=proposal.rule_ids,
            approved_by=reviewer,
            approved_at=timestamp,
            comment=comment.strip(),
        )

    def prepare_patch(
        self,
        *,
        fragment: WorkProductFragment,
        proposal: ReviewedRedraftProposal,
        approval: LawyerApprovalRecord,
    ) -> ControlledFragmentPatch:
        if fragment.fragment_id != proposal.fragment_id:
            raise ValueError("Proposal fragment_id does not match target fragment")
        if approval.fragment_id != fragment.fragment_id:
            raise ValueError("Approval fragment_id does not match target fragment")
        if proposal.original_text != fragment.text:
            raise ValueError("Fragment text changed since proposal generation; re-review required")

        proposal_hash = self.proposal_hash(proposal)
        if approval.proposal_hash != proposal_hash:
            raise ValueError("Approval does not bind the supplied proposal")
        if approval.approved_text_hash != self._hash(proposal.proposed_text):
            raise ValueError("Approved text hash does not match proposal")
        if approval.authority_ids != proposal.authority_ids:
            raise ValueError("Approval authority set differs from proposal")
        if approval.rule_ids != proposal.rule_ids:
            raise ValueError("Approval rule set differs from proposal")

        original_hash = self._hash(fragment.text)
        replacement_hash = self._hash(proposal.proposed_text)
        patch_id = f"patch:{fragment.fragment_id}:{original_hash[:8]}:{replacement_hash[:8]}"
        return ControlledFragmentPatch(
            patch_id=patch_id,
            fragment_id=fragment.fragment_id,
            work_product_id=fragment.work_product_id,
            original_text_hash=original_hash,
            replacement_text=proposal.proposed_text,
            replacement_text_hash=replacement_hash,
            approval_id=approval.approval_id,
            proposal_hash=proposal_hash,
            authority_ids=proposal.authority_ids,
            rule_ids=proposal.rule_ids,
            ready_for_explicit_apply=True,
        )

    @staticmethod
    def may_apply(patch: ControlledFragmentPatch) -> bool:
        """Return whether an explicit apply operation may be offered.

        This never performs mutation and never authorizes automatic application.
        """
        return patch.ready_for_explicit_apply and not patch.may_auto_apply

    @classmethod
    def proposal_hash(cls, proposal: ReviewedRedraftProposal) -> str:
        raw = "\n".join(
            (
                proposal.fragment_id,
                proposal.original_text,
                proposal.proposed_text,
                proposal.style.value,
                "|".join(proposal.authority_ids),
                "|".join(proposal.rule_ids),
            )
        )
        return cls._hash(raw)

    @staticmethod
    def _hash(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()
