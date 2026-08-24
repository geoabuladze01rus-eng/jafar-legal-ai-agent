from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .legal_entity_intelligence import LegalEntityIntelligence, SourceFinding


@dataclass(slots=True)
class LegalEntityDossier:
    query: str
    query_type: str
    generated_at: datetime
    profile: dict[str, Any]
    sources: list[SourceFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "query_type": self.query_type,
            "generated_at": self.generated_at.isoformat(),
            "profile": self.profile,
            "sources": [
                {
                    "source_key": item.source_key,
                    "status": item.status,
                    "title": item.title,
                    "details": item.details,
                    "source_url": item.source_url,
                }
                for item in self.sources
            ],
        }


class LegalEntityDossierBuilder:
    def __init__(self, intelligence: LegalEntityIntelligence | None = None) -> None:
        self.intelligence = intelligence or LegalEntityIntelligence()

    def build(self, query: str, query_type: str, findings: list[SourceFinding]) -> LegalEntityDossier:
        profile = self.intelligence.build_profile(findings)
        return LegalEntityDossier(
            query=query,
            query_type=query_type,
            generated_at=datetime.now(UTC),
            profile=profile,
            sources=findings,
        )
