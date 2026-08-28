from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .contradiction_detector import ContradictionGapDetector
from .council_review import CouncilReview


@dataclass(frozen=True, slots=True)
class CouncilEvidenceReport:
    claims: tuple[dict[str, Any], ...]
    contradictions: tuple[dict[str, Any], ...]
    evidence_gaps: tuple[str, ...]
    lawyer_questions: tuple[str, ...]
    malformed_providers: tuple[str, ...]
    requires_human_review: bool


class CouncilEvidenceService:
    """Convert structured council outputs into auditable evidence-review signals."""

    def __init__(self, detector: ContradictionGapDetector | None = None) -> None:
        self.detector = detector or ContradictionGapDetector()

    def build(self, review: CouncilReview) -> CouncilEvidenceReport:
        claims: list[dict[str, Any]] = []
        missing_evidence: list[str] = []
        lawyer_questions: list[str] = []
        malformed: list[str] = []

        for response in review.council.responses:
            payload = self._parse_payload(response.text)
            if payload is None:
                malformed.append(response.provider)
                continue

            for raw_claim in payload.get("claims", []):
                if not isinstance(raw_claim, dict):
                    continue
                topic = str(raw_claim.get("topic", "")).strip()
                statement = str(raw_claim.get("statement", "")).strip()
                position = str(raw_claim.get("position", "uncertain")).strip()
                evidence_ids = raw_claim.get("evidence_ids", [])
                if not topic or not statement:
                    continue
                if not isinstance(evidence_ids, list):
                    evidence_ids = []
                claims.append(
                    {
                        "topic": topic,
                        "statement": statement,
                        "position": position,
                        "evidence_ids": [str(item) for item in evidence_ids],
                        "provider": response.provider,
                    }
                )

            missing_evidence.extend(self._string_items(payload.get("missing_evidence", [])))
            lawyer_questions.extend(self._string_items(payload.get("lawyer_questions", [])))

        contradictions = self.detector.compare_claims(claims)
        serialized = tuple(self.detector.serialize(contradictions))
        gaps = tuple(dict.fromkeys(item for item in missing_evidence if item))
        questions = tuple(dict.fromkeys(item for item in lawyer_questions if item))
        malformed_providers = tuple(dict.fromkeys(malformed))
        requires_human_review = bool(serialized or gaps or questions or malformed_providers)

        return CouncilEvidenceReport(
            claims=tuple(claims),
            contradictions=serialized,
            evidence_gaps=gaps,
            lawyer_questions=questions,
            malformed_providers=malformed_providers,
            requires_human_review=requires_human_review,
        )

    @staticmethod
    def _parse_payload(text: str) -> dict[str, Any] | None:
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _string_items(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]
