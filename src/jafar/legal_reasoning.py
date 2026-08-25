from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
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
            confidence, confidence_invalid = self._safe_confidence(fact.get("confidence"))
            metadata = dict(fact.get("metadata") or {})
            source_type = fact.get("source_type")
            if source_type:
                metadata["source_type"] = str(source_type)
            if not basis:
                metadata["evidence_gap"] = True
            if confidence_invalid:
                metadata["confidence_invalid"] = True

            findings.append(
                LegalFinding(
                    "fact_assessment",
                    str(fact.get("statement", "")),
                    basis,
                    confidence,
                    confidence_invalid or confidence < 0.95 or not basis,
                    metadata,
                )
            )

        for risk in risks or []:
            risk_basis = tuple(
                str(item) for item in risk.get("evidence_ids", []) if item in evidence_ids
            )
            risk_confidence, confidence_invalid = self._safe_confidence(risk.get("confidence"))
            risk_metadata = dict(risk.get("metadata") or {})
            risk_metadata["severity"] = risk.get("severity")
            source_type = risk.get("source_type")
            if source_type:
                risk_metadata["source_type"] = str(source_type)
            if not risk_basis:
                risk_metadata["evidence_gap"] = True
            if confidence_invalid:
                risk_metadata["confidence_invalid"] = True

            findings.append(
                LegalFinding(
                    "risk_signal",
                    str(risk.get("statement", risk.get("title", ""))),
                    risk_basis,
                    risk_confidence,
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
    def _safe_confidence(value: Any) -> tuple[float, bool]:
        """Return a bounded confidence and whether the input was invalid.

        Model output is untrusted input. Malformed, missing, NaN or infinite values must not
        crash legal analysis or be promoted to a high-confidence conclusion.
        """
        try:
            confidence = float(value)
        except (TypeError, ValueError, OverflowError):
            return 0.0, True

        if not isfinite(confidence):
            return 0.0, True

        return max(0.0, min(1.0, confidence)), False

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
