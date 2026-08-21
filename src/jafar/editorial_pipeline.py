from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class ContentFormat(StrEnum):
    BREAKING = "breaking"
    EXPLAINER = "explainer"
    CASE = "case"
    POLL = "poll"
    Q_AND_A = "q_and_a"


@dataclass(frozen=True)
class NewsEvent:
    title: str
    summary: str
    source_url: str
    published_at: datetime
    official: bool = False
    legal_relevance: float = 0.0
    public_interest: float = 0.0
    novelty: float = 0.0

    def score(self) -> float:
        freshness = max(0.0, min(1.0, 1.0 - (datetime.now(timezone.utc) - self.published_at).total_seconds() / 172800))
        source_bonus = 0.15 if self.official else 0.0
        return min(1.0, 0.30 * self.legal_relevance + 0.25 * self.public_interest + 0.20 * self.novelty + 0.25 * freshness + source_bonus)


@dataclass(frozen=True)
class ContentIdea:
    title: str
    format: ContentFormat
    source_url: str | None
    score: float
    tags: tuple[str, ...] = field(default_factory=tuple)


def select_ideas(events: list[NewsEvent], limit: int = 5) -> list[ContentIdea]:
    ranked = sorted(events, key=NewsEvent.score, reverse=True)
    ideas: list[ContentIdea] = []
    for event in ranked[:limit]:
        score = event.score()
        fmt = ContentFormat.BREAKING if score >= 0.82 else ContentFormat.EXPLAINER
        ideas.append(ContentIdea(event.title, fmt, event.source_url, score, ("право", "уголовный процесс")))
    return ideas
