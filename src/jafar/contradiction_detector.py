from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Contradiction:
    topic: str
    left: str
    right: str
    evidence_ids: tuple[str, ...]
    severity: str = "medium"


@dataclass(frozen=True, slots=True)
class EvidenceGap:
    topic: str
    description: str
    expected_evidence: tuple[str, ...]
    severity: str = "medium"


class ContradictionGapDetector:
    """Flags explicit conflicts and missing evidence; it does not decide legal truth."""

    def compare_claims(self, claims: list[dict[str, Any]]) -> list[Contradiction]:
        by_topic: dict[str, list[dict[str, Any]]] = {}
        for claim in claims:
            by_topic.setdefault(str(claim.get("topic", "unknown")), []).append(claim)

        result: list[Contradiction] = []
        for topic, items in by_topic.items():
            for index, left in enumerate(items):
                for right in items[index + 1 :]:
                    if left.get("statement") != right.get("statement") and left.get("position") != right.get("position"):
                        result.append(Contradiction(
                            topic=topic,
                            left=str(left.get("statement", "")),
                            right=str(right.get("statement", "")),
                            evidence_ids=tuple(dict.fromkeys([*(left.get("evidence_ids", [])), *(right.get("evidence_ids", []))])),
                            severity="high",
                        ))
        return result

    def find_gaps(self, claims: list[dict[str, Any]], required_topics: list[str]) -> list[EvidenceGap]:
        present = {str(claim.get("topic")) for claim in claims}
        return [
            EvidenceGap(topic=topic, description="Недостаточно подтверждающих материалов", expected_evidence=(topic,), severity="medium")
            for topic in required_topics if topic not in present
        ]

    @staticmethod
    def serialize(items: list[Contradiction | EvidenceGap]) -> list[dict[str, Any]]:
        return [
            {"type": "contradiction", "topic": item.topic, "left": item.left, "right": item.right, "evidence_ids": list(item.evidence_ids), "severity": item.severity}
            if isinstance(item, Contradiction)
            else {"type": "evidence_gap", "topic": item.topic, "description": item.description, "expected_evidence": list(item.expected_evidence), "severity": item.severity}
            for item in items
        ]
