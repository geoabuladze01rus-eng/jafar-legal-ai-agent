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
        evidence_ids = {
            evidence_id
            for item in evidence
            if isinstance(item, dict)
            for evidence_id in self._normalize_ids(item.get("evidence_id"))
        }
        findings: list[LegalFinding] = []
        evidence_gaps: list[LegalFinding] = []

        for fact in facts:
            if not isinstance(fact, dict):
                continue
            statement = str(fact.get("statement", ""))
            requested_ids = self._normalize_ids(fact.get("evidence_ids"))
            basis = tuple(item for item in requested_ids if item in evidence_ids)
            missing_ids = tuple(item for item in requested_ids if item not in evidence_ids)
            raw_confidence = fact.get("confidence")
            confidence = self._confidence(raw_confidence)
            confidence_invalid = self._confidence_invalid(raw_confidence)
            metadata = self._finding_metadata(fact.get("metadata"), missing_ids)
            source_type = str(fact.get("source_type")) if fact.get("source_type") else None
            if source_type:
                metadata["source_type"] = source_type
            if not basis:
                metadata["evidence_gap"] = True
            if confidence_invalid:
                metadata["confidence_invalid"] = True
            findings.append(
                LegalFinding(
                    "fact_assessment",
                    statement,
                    basis,
                    confidence,
                    (
                        confidence_invalid
                        or confidence < 0.95
                        or not basis
                        or bool(missing_ids)
                        or self._source_requires_human_review(source_type)
                    ),
                    metadata,
                )
            )
            self._record_evidence_gap(
                evidence_gaps,
                source_kind="fact",
                statement=statement,
                requested_ids=requested_ids,
                missing_ids=missing_ids,
                confidence=confidence,
            )

        for risk in risks or []:
            if not isinstance(risk, dict):
                continue
            statement = str(risk.get("statement", risk.get("title", "")))
            requested_ids = self._normalize_ids(risk.get("evidence_ids"))
            basis = tuple(item for item in requested_ids if item in evidence_ids)
            missing_ids = tuple(item for item in requested_ids if item not in evidence_ids)
            raw_confidence = risk.get("confidence")
            confidence = self._confidence(raw_confidence)
            confidence_invalid = self._confidence_invalid(raw_confidence)
            metadata = self._finding_metadata(
                risk.get("metadata"),
                missing_ids,
                severity=risk.get("severity"),
            )
            source_type = risk.get("source_type")
            if source_type:
                metadata["source_type"] = str(source_type)
            if not basis:
                metadata["evidence_gap"] = True
            if confidence_invalid:
                metadata["confidence_invalid"] = True
            findings.append(
                LegalFinding(
                    "risk_signal",
                    statement,
                    basis,
                    confidence,
                    True,
                    metadata,
                )
            )
            self._record_evidence_gap(
                evidence_gaps,
                source_kind="risk",
                statement=statement,
                requested_ids=requested_ids,
                missing_ids=missing_ids,
                confidence=confidence,
            )

        chronology = sorted(timeline or [], key=lambda event: str(event.get("event_at") or ""))
        grounded_findings = sum(bool(item.basis) for item in findings)
        return {
            "findings": [self._serialize(item) for item in findings],
            "evidence_gaps": [self._serialize(item) for item in evidence_gaps],
            "evidence_coverage": {
                "grounded_findings": grounded_findings,
                "ungrounded_findings": len(findings) - grounded_findings,
                "missing_evidence_references": sum(
                    len(item.metadata.get("missing_evidence_ids", []))
                    for item in evidence_gaps
                    if item.kind == "missing_referenced_evidence"
                ),
            },
            "timeline": chronology,
            "human_review_required": True,
            "evidence_count": len(evidence),
            "disclaimer": (
                "AI output is an analytical aid and requires review by a qualified lawyer "
                "before legal reliance or external action."
            ),
        }

    @classmethod
    def _record_evidence_gap(
        cls,
        gaps: list[LegalFinding],
        *,
        source_kind: str,
        statement: str,
        requested_ids: tuple[str, ...],
        missing_ids: tuple[str, ...],
        confidence: float,
    ) -> None:
        if missing_ids:
            gaps.append(
                LegalFinding(
                    "missing_referenced_evidence",
                    statement,
                    (),
                    confidence,
                    True,
                    {
                        "source_kind": source_kind,
                        "missing_evidence_ids": list(missing_ids),
                    },
                )
            )
        elif not requested_ids:
            gaps.append(
                LegalFinding(
                    "ungrounded_fact" if source_kind == "fact" else "ungrounded_risk",
                    statement,
                    (),
                    confidence,
                    True,
                    {"source_kind": source_kind, "missing_evidence_ids": []},
                )
            )

    @classmethod
    def _normalize_ids(cls, value: Any) -> tuple[str, ...]:
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            values = (value,)
        elif isinstance(value, (list, tuple, set, frozenset)):
            values = value
        else:
            return ()

        normalized: list[str] = []
        seen: set[str] = set()
        for item in values:
            evidence_id = cls._normalize_id(item)
            if evidence_id is None or evidence_id in seen:
                continue
            normalized.append(evidence_id)
            seen.add(evidence_id)
        return tuple(normalized)

    @staticmethod
    def _normalize_id(value: Any) -> str | None:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float) and isfinite(value):
            return str(int(value)) if value.is_integer() else format(value, "g")
        return None

    @staticmethod
    def _confidence(value: Any) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError, OverflowError):
            return 0.0
        if not isfinite(confidence):
            return 0.0
        return max(0.0, min(1.0, confidence))

    @staticmethod
    def _confidence_invalid(value: Any) -> bool:
        try:
            confidence = float(value)
        except (TypeError, ValueError, OverflowError):
            return True
        return not isfinite(confidence)

    @staticmethod
    def _source_requires_human_review(source_type: str | None) -> bool:
        return bool(source_type and source_type != "document_fact")

    @staticmethod
    def _finding_metadata(
        value: Any,
        missing_ids: tuple[str, ...],
        **additional: Any,
    ) -> dict[str, Any]:
        metadata = dict(value) if isinstance(value, dict) else {}
        metadata.update(additional)
        metadata["missing_evidence_ids"] = list(missing_ids)
        return metadata

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
