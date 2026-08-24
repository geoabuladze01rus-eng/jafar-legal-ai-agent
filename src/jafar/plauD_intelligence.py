# ruff: noqa: N999 - retained for compatibility with the original public module path.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AudioEvidence:
    recording_id: str
    source: str
    file_name: str | None
    duration_seconds: float | None
    transcript: str
    participants: tuple[str, ...]
    facts: tuple[dict[str, Any], ...]
    confidence: float


class PlaudIntelligence:
    """Normalizes PLAUD recordings for the common evidence/timeline pipeline."""

    source = "plaud"

    def ingest(self, payload: dict[str, Any]) -> AudioEvidence:
        participants = tuple(str(item) for item in payload.get("participants", []) if item)
        facts = tuple(item for item in payload.get("facts", []) if isinstance(item, dict))
        return AudioEvidence(
            recording_id=str(payload.get("recording_id", "")),
            source=self.source,
            file_name=payload.get("file_name"),
            duration_seconds=payload.get("duration_seconds"),
            transcript=str(payload.get("transcript", "")),
            participants=participants,
            facts=facts,
            confidence=float(payload.get("confidence", 0.0)),
        )

    @staticmethod
    def timeline_candidates(evidence: AudioEvidence) -> list[dict[str, Any]]:
        return [
            {
                "event_type": "audio_fact",
                "title": fact.get("title") or "Факт из аудиозаписи",
                "description": fact.get("description"),
                "actor_refs": list(evidence.participants),
                "evidence_source": evidence.source,
                "confidence": evidence.confidence,
            }
            for fact in evidence.facts
        ]
