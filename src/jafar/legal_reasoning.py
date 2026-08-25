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

    def analyze(
        self,
        *,
        facts: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        risks: list[dict[str, Any]] | None = None,
        timeline: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        evidence_ids = {item.get("evidence_id") for item in evidence if item.get("evidence_id")}
        findings: list[LegalFinding] = []

        for fact in facts:
            basis = tuple(
                str(item) for item in fact.get("evidence_ids", []) if item in evidence_ids
            )
            confidence = max(0.0, min(1.0, float(fact.get("confidence", 0.0))))
            metadata = dict(fact.get("metadata") or {})
            source_type = fact.get("source_type")
            if source_type:
                metadata["source_type"] = str(source_type)
            if not basis:
                metadata["evidence_gap"] = True

            findings.append(
                LegalFinding(
                    "fact_assessment",
                    str(fact.get("statement", "")),
                    basis,
                    confidence,
                    confidence < 0.95 or not basis,
                    metadata,
                )
            )

        for risk in risks or []:
            risk_metadata = dict(risk.get("metadata") or {})
            risk_metadata["severity"] = risk.get("severity")
            source_type = risk.get("source_type")
            if source_type:
                risk_metadata["source_type"] = str(source_type)
            findings.append(
                LegalFinding(
                    "risk_signal",
                    str(risk.get("statement", risk.get("title", ""))),
                    tuple(
                        str(item)
                        for item in risk.get("evidence_ids", [])
                        if item in evidence_ids
                    ),
                    max(0.0, min(1.0, float(risk.get("confidence", 0.0)))),
                    True,
                    risk_metadata,
                )
            )

        chronology = sorted(timeline or [], key=lambda event: str(event.get("event_at") or ""))
        return {
            "findings": [self._serialize(item) for item in findings],
            "timeline": chronology,
            "human_review_required": True,
            "evidence_count": len(evidence),
            "disclaimer": (
                "AI output is an analytical aid and requires review by a qualified lawyer "
                "before legal reliance or external action."
            ),
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
