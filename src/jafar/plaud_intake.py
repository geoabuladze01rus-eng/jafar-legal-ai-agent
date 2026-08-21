from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class PlaudRecording:
    recording_id: str
    title: str
    transcript: str
    recorded_at: datetime
    source_url: str | None = None


@dataclass(frozen=True, slots=True)
class PlaudFinding:
    kind: str
    text: str
    confidence: float
    metadata: dict[str, Any]


class PlaudTranscriptAnalyzer(Protocol):
    def analyze(self, transcript: str) -> list[PlaudFinding]: ...


class PlaudIntakeService:
    """Normalizes PLAUD transcripts before they enter Jafar's case workflow."""

    def __init__(self, analyzer: PlaudTranscriptAnalyzer) -> None:
        self.analyzer = analyzer

    def ingest(self, recording: PlaudRecording) -> dict[str, Any]:
        findings = self.analyzer.analyze(recording.transcript)
        return {
            "recording_id": recording.recording_id,
            "title": recording.title,
            "recorded_at": recording.recorded_at.isoformat(),
            "source_url": recording.source_url,
            "findings": [
                {
                    "kind": finding.kind,
                    "text": finding.text,
                    "confidence": finding.confidence,
                    "metadata": finding.metadata,
                }
                for finding in findings
            ],
        }
