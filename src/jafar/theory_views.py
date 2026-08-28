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
    """Project one source-backed theory map into prosecution and defense views.

    The view classifies arguments; it does not decide which side is legally correct.
    """

    PROSECUTION_POSITIONS = {
        "prosecution",
        "accusation",
        "guilt",
        "supports_guilt",
        "supports_prosecution",
        "occurred",
        "present",
        "yes",
    }
    DEFENSE_POSITIONS = {
        "defense",
        "innocence",
        "supports_defense",
        "opposes_prosecution",
        "did_not_occur",
        "absent",
        "no",
    }

    def build(self, report: CaseTheoryReport) -> DualTheoryReport:
        prosecution: list[TheoryViewItem] = []
        defense: list[TheoryViewItem] = []
        neutral: list[TheoryViewItem] = []

        for issue in report.issues:
            side = self._classify(issue)
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

    def _classify(self, issue: CaseTheoryIssue) -> TheorySide:
        position = issue.position.strip().casefold()
        if position in self.PROSECUTION_POSITIONS:
            return TheorySide.PROSECUTION
        if position in self.DEFENSE_POSITIONS:
            return TheorySide.DEFENSE
        return TheorySide.NEUTRAL

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
                source
                for item in prosecution_items
                for source in item.source_refs
            )
            defense_sources = tuple(
                source
                for item in defense_items
                for source in item.source_refs
            )
            defense_challenges = bool(
                defense_items
                and all(item.evidence_ids for item in defense_items)
                and any(
                    item.status in {TheoryStatus.CONTRADICTED, TheoryStatus.REVIEW_REQUIRED, TheoryStatus.SUPPORTED}
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
