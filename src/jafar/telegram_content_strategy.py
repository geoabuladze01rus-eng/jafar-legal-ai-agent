from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, Sequence
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, Field


class ContentPillar(StrEnum):
    PRACTICE_CASE = "practice_case"
    CRIMINAL_PROCEDURE = "criminal_procedure"
    INVESTIGATOR_LOGIC = "investigator_logic"
    WHAT_TO_DO = "what_to_do"
    INVESTIGATION_ERROR = "investigation_error"
    COURT_PRACTICE = "court_practice"
    NEWS_ANALYSIS = "news_analysis"
    PERSONAL_BRAND = "personal_brand"


class SourceItem(BaseModel):
    title: str
    url: str
    summary: str = ""
    source_name: str = ""
    published_at: str | None = None

    @property
    def fingerprint(self) -> str:
        seed = f"{canonical_url(self.url)}\x1f{_normalize(self.title)}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()


class SourceMonitor(Protocol):
    def collect(self) -> Sequence[SourceItem]: ...


@dataclass(slots=True)
class AggregatingSourceMonitor:
    providers: Sequence[SourceMonitor]

    def collect(self) -> list[SourceItem]:
        items: list[SourceItem] = []
        seen: set[str] = set()
        for provider in self.providers:
            for item in provider.collect():
                if item.fingerprint in seen:
                    continue
                seen.add(item.fingerprint)
                items.append(item)
        return items


class TopicDimensions(BaseModel):
    relevance: int = Field(ge=0, le=100)
    legal_value: int = Field(ge=0, le=100)
    practical_value: int = Field(ge=0, le=100)
    author_unique_angle: int = Field(ge=0, le=100)
    shareability: int = Field(ge=0, le=100)
    timeliness: int = Field(ge=0, le=100)
    risk: int = Field(ge=0, le=100)
    duplication: int = Field(ge=0, le=100)


class TopicCandidate(BaseModel):
    candidate_id: str
    title: str
    pillar: ContentPillar
    source_url: str | None = None
    is_news: bool = False
    dimensions: TopicDimensions


class TopicScore(BaseModel):
    score: int = Field(ge=0, le=100)
    eligible: bool
    reasons: list[str] = Field(default_factory=list)


class TopicScorer:
    """Deterministic score. Inputs must come from real evidence/model review, never invented here."""

    POSITIVE_WEIGHTS = {
        "relevance": 0.24,
        "legal_value": 0.16,
        "practical_value": 0.20,
        "author_unique_angle": 0.16,
        "shareability": 0.12,
        "timeliness": 0.12,
    }

    def score(self, candidate: TopicCandidate, *, threshold: int = 65) -> TopicScore:
        d = candidate.dimensions
        raw = sum(getattr(d, key) * weight for key, weight in self.POSITIVE_WEIGHTS.items())
        penalty = d.risk * 0.20 + d.duplication * 0.20
        final = max(0, min(100, round(raw - penalty)))

        reasons: list[str] = []
        if final < threshold:
            reasons.append("score_below_threshold")
        if d.risk >= 70:
            reasons.append("risk_too_high")
        if d.duplication >= 70:
            reasons.append("too_similar_to_recent_content")
        if candidate.is_news and d.author_unique_angle < 50:
            reasons.append("news_lacks_author_unique_angle")
        if d.relevance < 50:
            reasons.append("low_channel_relevance")
        return TopicScore(score=final, eligible=not reasons, reasons=reasons)


class PlannedSlot(BaseModel):
    day_index: int = Field(ge=1, le=7)
    candidate_id: str
    pillar: ContentPillar
    score: int


class SevenDayPlanner:
    """Select up to one evidence-backed candidate per day while avoiding monotony."""

    def __init__(self, scorer: TopicScorer | None = None) -> None:
        self.scorer = scorer or TopicScorer()

    def plan(self, candidates: Sequence[TopicCandidate]) -> list[PlannedSlot]:
        ranked: list[tuple[TopicCandidate, TopicScore]] = []
        for candidate in candidates:
            score = self.scorer.score(candidate)
            if score.eligible:
                ranked.append((candidate, score))
        ranked.sort(key=lambda item: (-item[1].score, item[0].candidate_id))

        chosen: list[tuple[TopicCandidate, TopicScore]] = []
        remaining = ranked[:]
        while remaining and len(chosen) < 7:
            previous_pillar = chosen[-1][0].pillar if chosen else None
            index = next(
                (i for i, (candidate, _) in enumerate(remaining) if candidate.pillar != previous_pillar),
                0,
            )
            chosen.append(remaining.pop(index))

        return [
            PlannedSlot(
                day_index=index,
                candidate_id=candidate.candidate_id,
                pillar=candidate.pillar,
                score=score.score,
            )
            for index, (candidate, score) in enumerate(chosen, start=1)
        ]


class ImagePromptGenerator:
    """Brand-safe visual direction; never inserts real case participants or fake evidence."""

    BASE_STYLE = (
        "serious cinematic editorial illustration, dark graphite and deep blue palette, "
        "black and cold grey, restrained gold or red accents, realistic legal atmosphere, "
        "documents and courthouse or investigator office motifs, no readable fake evidence, "
        "no logos, no identifiable real people, no text rendered inside the image"
    )

    def generate(self, *, topic: str, pillar: ContentPillar) -> str:
        safe_topic = re.sub(r"\b[A-ZА-ЯЁ][a-zа-яё]+\s+[A-ZА-ЯЁ][a-zа-яё]+\b", "anonymous person", topic)
        safe_topic = re.sub(r"\s+", " ", safe_topic).strip()[:300]
        return f"{self.BASE_STYLE}; theme: {pillar.value}; concept: {safe_topic}"


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    netloc = host
    if parts.port:
        netloc = f"{host}:{parts.port}"
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), netloc, path, "", ""))


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())
