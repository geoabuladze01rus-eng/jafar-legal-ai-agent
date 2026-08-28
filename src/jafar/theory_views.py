from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .case_theory import CaseTheoryIssue, CaseTheoryReport, TheoryStatus


class TheorySide(StrEnum):
    PROSECUTION = "prosecution"
    DEFENSE = "defense"
    NEUTRAL = "neutral"


@dataclass(frozen=True, slots=True)
class TheorySideAssignment:
    issue_id: str
    side: TheorySide
    assigned_by: str = "lawyer"
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class TheoryViewItem:
    issue_id: str
    topic: str
    statement: str
    side: TheorySide
    status: TheoryStatus
    evidence_ids: tuple[str, ...]
    source_refs: tuple[dict[str, Any], ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TheoryConflictPoint:
    topic: str
    prosecution_issue_ids: tuple[str, ...]
    defense_issue_ids: tuple[str, ...]
    prosecution_sources: tuple[dict[str, Any], ...]
    defense_sources: tuple[dict[str, Any], ...]
    defense_challenges_prosecution: bool
    requires_human_review: bool = True


@dataclass(frozen=True, slots=True)
class DualTheoryReport:
    prosecution: tuple[TheoryViewItem, ...]
    defense: tuple[TheoryViewItem, ...]
    neutral: tuple[TheoryViewItem, ...]
    conflict_points: tuple[TheoryConflictPoint, ...]
    requires_human_review: bool


class ProsecutionDefenseTheoryView:
    """Project a source-backed theory map into explicit prosecution/defense views.

    Side assignment is never inferred from generic claim positions such as `present`,
    `occurred`, `yes`, `absent` or `no`. Missing assignments remain neutral.
    """

    def build(
        self,
        report: CaseTheoryReport,
        assignments: tuple[TheorySideAssignment, ...] = (),
    ) -> DualTheoryReport:
        assignment_index = self._assignment_index(report, assignments)
        prosecution: list[TheoryViewItem] = []
        defense: list[TheoryViewItem] = []
        neutral: list[TheoryViewItem] = []

        for issue in report.issues:
            side = assignment_index.get(issue.issue_id, TheorySide.NEUTRAL)
            item = self._item(issue, side)
            if side == TheorySide.PROSECUTION:
                prosecution.append(item)
            elif side == TheorySide.DEFENSE:
                defense.append(item)
            else:
                neutral.append(item)

        conflicts = self._conflict_points(prosecution, defense)
        requires_human_review = report.requires_human_review or bool(conflicts)
        return DualTheoryReport(
            prosecution=tuple(prosecution),
            defense=tuple(defense),
            neutral=tuple(neutral),
            conflict_points=conflicts,
            requires_human_review=requires_human_review,
        )

    def snapshot(self, report: DualTheoryReport) -> dict[str, Any]:
        return {
            "prosecution": [self._serialize_item(item) for item in report.prosecution],
            "defense": [self._serialize_item(item) for item in report.defense],
            "neutral": [self._serialize_item(item) for item in report.neutral],
            "conflict_points": [
                {
                    "topic": item.topic,
                    "prosecution_issue_ids": list(item.prosecution_issue_ids),
                    "defense_issue_ids": list(item.defense_issue_ids),
                    "prosecution_sources": list(item.prosecution_sources),
                    "defense_sources": list(item.defense_sources),
                    "defense_challenges_prosecution": item.defense_challenges_prosecution,
                    "requires_human_review": item.requires_human_review,
                }
                for item in report.conflict_points
            ],
            "requires_human_review": report.requires_human_review,
        }

    @staticmethod
    def _assignment_index(
        report: CaseTheoryReport,
        assignments: tuple[TheorySideAssignment, ...],
    ) -> dict[str, TheorySide]:
        valid_ids = {issue.issue_id for issue in report.issues}
        result: dict[str, TheorySide] = {}
        for assignment in assignments:
            if assignment.issue_id not in valid_ids:
                raise ValueError(f"Unknown theory issue_id: {assignment.issue_id}")
            if assignment.issue_id in result:
                raise ValueError(f"Duplicate theory side assignment: {assignment.issue_id}")
            if assignment.side != TheorySide.NEUTRAL and not assignment.assigned_by.strip():
                raise ValueError("Non-neutral theory side assignment requires assigned_by")
            result[assignment.issue_id] = assignment.side
        return result

    @staticmethod
    def _item(issue: CaseTheoryIssue, side: TheorySide) -> TheoryViewItem:
        return TheoryViewItem(
            issue_id=issue.issue_id,
            topic=issue.topic,
            statement=issue.statement,
            side=side,
            status=issue.status,
            evidence_ids=issue.evidence_ids,
            source_refs=issue.source_refs,
            reasons=issue.reasons,
        )

    @staticmethod
    def _conflict_points(
        prosecution: list[TheoryViewItem],
        defense: list[TheoryViewItem],
    ) -> tuple[TheoryConflictPoint, ...]:
        prosecution_by_topic: dict[str, list[TheoryViewItem]] = {}
        defense_by_topic: dict[str, list[TheoryViewItem]] = {}
        for item in prosecution:
            prosecution_by_topic.setdefault(item.topic, []).append(item)
        for item in defense:
            defense_by_topic.setdefault(item.topic, []).append(item)

        result: list[TheoryConflictPoint] = []
        for topic in sorted(set(prosecution_by_topic) & set(defense_by_topic)):
            prosecution_items = prosecution_by_topic[topic]
            defense_items = defense_by_topic[topic]
            prosecution_sources = tuple(
                source for item in prosecution_items for source in item.source_refs
            )
            defense_sources = tuple(
                source for item in defense_items for source in item.source_refs
            )
            defense_challenges = bool(
                defense_items
                and all(item.evidence_ids for item in defense_items)
                and any(
                    item.status
                    in {
                        TheoryStatus.CONTRADICTED,
                        TheoryStatus.REVIEW_REQUIRED,
                        TheoryStatus.SUPPORTED,
                    }
                    for item in prosecution_items
                )
            )
            result.append(
                TheoryConflictPoint(
                    topic=topic,
                    prosecution_issue_ids=tuple(item.issue_id for item in prosecution_items),
                    defense_issue_ids=tuple(item.issue_id for item in defense_items),
                    prosecution_sources=prosecution_sources,
                    defense_sources=defense_sources,
                    defense_challenges_prosecution=defense_challenges,
                )
            )
        return tuple(result)

    @staticmethod
    def _serialize_item(item: TheoryViewItem) -> dict[str, Any]:
        return {
            "issue_id": item.issue_id,
            "topic": item.topic,
            "statement": item.statement,
            "side": item.side.value,
            "status": item.status.value,
            "evidence_ids": list(item.evidence_ids),
            "source_refs": list(item.source_refs),
            "reasons": list(item.reasons),
        }
