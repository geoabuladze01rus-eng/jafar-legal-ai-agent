from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class LegalFinding:
    kind: str
    statement: str
    basis: tuple[str, ...]
    confidence: float
    requires_human_review: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class LegalReasoningEngine:
    """Evidence-grounded reasoning layer; never presents inference as established fact."""

    def analyze(self, *, facts: list[dict[str, Any]], evidence: list[dict[str, Any]], risks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        evidence_ids = {item.get("evidence_id") for item in evidence if item.get("evidence_id")}
        findings: list[LegalFinding] = []

        for fact in facts:
            basis = tuple(str(item) for item in fact.get("evidence_ids", []) if item in evidence_ids)
            confidence = float(fact.get("confidence", 0.0))
            findings.append(LegalFinding(
                kind="fact_assessment",
                statement=str(fact.get("statement", "")),
                basis=basis,
                confidence=confidence,
                requires_human_review=confidence < 0.95 or not basis,
            ))

        for risk in risks or []:
            findings.append(LegalFinding(
                kind="risk_signal",
                statement=str(risk.get("statement", risk.get("title", ""))),
                basis=tuple(str(item) for item in risk.get("evidence_ids", []) if item in evidence_ids),
                confidence=float(risk.get("confidence", 0.0)),
                requires_human_review=True,
                metadata={"severity": risk.get("severity")},
            ))

        return {
            "findings": [self._serialize(item) for item in findings],
            "human_review_required": any(item.requires_human_review for item in findings),
            "evidence_count": len(evidence),
        }

    @staticmethod
    def _serialize(item: LegalFinding) -> dict[str, Any]:
        return {
            "kind": item.kind,
            "statement": item.statement,
            "basis": list(item.basis),
            "confidence": item.confidence,
            "requires_human_review": item.requires_human_review,
            "metadata": item.metadata,
        }
