from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from .safe_fragment_redrafting import FragmentRedraftPacket


class ProposalStyle(StrEnum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    assertive = "assertive"


@dataclass(frozen=True, slots=True)
class VerifiedRedraftAuthority:
    authority_id: str
    citation: str
    proposition: str
    source_url: str
    rule_ids: tuple[str, ...] = ()
    verified: bool = True
    applicable: bool = True
    current: bool = True


@dataclass(frozen=True, slots=True)
class RedraftProposalCandidate:
    style: ProposalStyle
    proposed_text: str
    rationale: str
    authority_ids: tuple[str, ...]
    rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReviewedRedraftProposal:
    fragment_id: str
    original_text: str
    proposed_text: str
    style: ProposalStyle
    rationale: str
    authority_ids: tuple[str, ...]
    rule_ids: tuple[str, ...]
    diff_lines: tuple[str, ...]
    passed_authority_gate: bool
    passed_source_ref_gate: bool
    may_auto_apply: bool = False
    requires_lawyer_approval: bool = True


@dataclass(frozen=True, slots=True)
class ReviewedRedraftReport:
    fragment_id: str
    proposals: tuple[ReviewedRedraftProposal, ...]
    blocked_reasons: tuple[str, ...]
    may_replace_fragment: bool
    requires_lawyer_review: bool


class RedraftProposalGenerator(Protocol):
    def generate(
        self,
        *,
        packet: FragmentRedraftPacket,
        authorities: tuple[VerifiedRedraftAuthority, ...],
        max_options: int,
    ) -> tuple[RedraftProposalCandidate, ...]: ...


class ReviewedRedraftProposalEngine:
    """Validate bounded redraft proposals without ever auto-applying them.

    Generation is injected so model choice is separate from legal safety. The engine checks
    that all relied-on authorities are verified, applicable and current and that the proposal
    stays tied to the original fragment's explicit source trail.
    """

    def __init__(self, generator: RedraftProposalGenerator) -> None:
        self.generator = generator

    def propose(
        self,
        *,
        packet: FragmentRedraftPacket,
        authorities: tuple[VerifiedRedraftAuthority, ...],
        max_options: int = 3,
    ) -> ReviewedRedraftReport:
        if max_options < 1 or max_options > 3:
            raise ValueError("max_options must be between 1 and 3")

        blocked = self._authority_blockers(packet, authorities)
        if blocked:
            return ReviewedRedraftReport(
                fragment_id=packet.fragment_id,
                proposals=(),
                blocked_reasons=blocked,
                may_replace_fragment=False,
                requires_lawyer_review=True,
            )

        candidates = self.generator.generate(
            packet=packet,
            authorities=authorities,
            max_options=max_options,
        )[:max_options]
        allowed_authorities = {item.authority_id for item in authorities}
        allowed_rules = {
            rule_id
            for item in authorities
            for rule_id in item.rule_ids
        }.union(packet.rule_ids)

        proposals: list[ReviewedRedraftProposal] = []
        proposal_blockers: list[str] = []
        for candidate in candidates:
            if not candidate.proposed_text.strip():
                proposal_blockers.append("Generator returned an empty proposed text.")
                continue
            if not set(candidate.authority_ids).issubset(allowed_authorities):
                proposal_blockers.append(
                    "Proposal cited an authority that did not pass the reviewed authority gate."
                )
                continue
            if candidate.rule_ids and not set(candidate.rule_ids).issubset(allowed_rules):
                proposal_blockers.append(
                    "Proposal relied on a normalized rule outside the reviewed rule set."
                )
                continue
            source_gate = bool(packet.source_refs)
            if not source_gate:
                proposal_blockers.append(
                    "Original fragment has no explicit source_refs; factual redraft cannot be safely released."
                )
            proposals.append(
                ReviewedRedraftProposal(
                    fragment_id=packet.fragment_id,
                    original_text=packet.original_text,
                    proposed_text=candidate.proposed_text.strip(),
                    style=candidate.style,
                    rationale=candidate.rationale,
                    authority_ids=candidate.authority_ids,
                    rule_ids=candidate.rule_ids,
                    diff_lines=self._diff(packet.original_text, candidate.proposed_text),
                    passed_authority_gate=True,
                    passed_source_ref_gate=source_gate,
                )
            )

        return ReviewedRedraftReport(
            fragment_id=packet.fragment_id,
            proposals=tuple(proposals),
            blocked_reasons=tuple(dict.fromkeys(proposal_blockers)),
            may_replace_fragment=False,
            requires_lawyer_review=True,
        )

    @staticmethod
    def release_ready(report: ReviewedRedraftReport) -> bool:
        """A proposal is review-ready, never replacement-ready.

        Returning True means at least one proposal passed machine gates and may be shown to
        the lawyer. It does not authorize mutation of the source document.
        """
        return bool(report.proposals) and all(
            item.passed_authority_gate and item.passed_source_ref_gate
            for item in report.proposals
        )

    @staticmethod
    def _authority_blockers(
        packet: FragmentRedraftPacket,
        authorities: tuple[VerifiedRedraftAuthority, ...],
    ) -> tuple[str, ...]:
        blockers: list[str] = []
        if packet.may_auto_apply:
            blockers.append("Unsafe packet: may_auto_apply must remain false.")
        if not authorities:
            blockers.append("No reviewed current authorities supplied for redraft.")
            return tuple(blockers)
        for authority in authorities:
            if not authority.verified:
                blockers.append(f"Authority {authority.authority_id} is not verified.")
            if not authority.applicable:
                blockers.append(f"Authority {authority.authority_id} is not applicable.")
            if not authority.current:
                blockers.append(f"Authority {authority.authority_id} is not current.")
            if not authority.source_url.strip():
                blockers.append(f"Authority {authority.authority_id} has no canonical source URL.")
        return tuple(dict.fromkeys(blockers))

    @staticmethod
    def _diff(original: str, proposed: str) -> tuple[str, ...]:
        import difflib

        return tuple(
            difflib.ndiff(
                original.splitlines() or [original],
                proposed.splitlines() or [proposed],
            )
        )
