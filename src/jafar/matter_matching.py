from __future__ import annotations

import re
from dataclasses import dataclass

from .legal_models import Matter

_TOKEN_RE = re.compile(r"[\wА-Яа-яЁё-]{3,}", re.UNICODE)


@dataclass(frozen=True)
class MatterMatch:
    matter_id: str
    score: float
    reasons: tuple[str, ...]


class MatterMatcher:
    """Conservative local matcher for assigning incoming documents to matters.

    Exact case-number matches dominate. Names and title tokens provide supporting
    evidence. Low-confidence matches are intentionally left unresolved.
    """

    def __init__(self, minimum_score: float = 0.55) -> None:
        self.minimum_score = minimum_score

    def match(self, text: str, matters: list[Matter]) -> list[MatterMatch]:
        if not text.strip() or not matters:
            return []
        normalized = text.casefold()
        results: list[MatterMatch] = []
        for matter in matters:
            score = 0.0
            reasons: list[str] = []
            if matter.case_number and matter.case_number.casefold() in normalized:
                score += 0.85
                reasons.append("exact case number")
            for label, value, weight in (
                ("client", matter.client_name, 0.25),
                ("opposing party", matter.opposing_party, 0.25),
                ("court/authority", matter.court_or_authority, 0.15),
                ("matter title", matter.title, 0.15),
            ):
                if not value:
                    continue
                tokens = set(_TOKEN_RE.findall(value.casefold()))
                hits = [token for token in tokens if token in normalized]
                if hits:
                    contribution = min(weight, weight * len(hits) / max(1, len(tokens)))
                    score += contribution
                    reasons.append(f"{label}: {', '.join(sorted(hits)[:3])}")
            if score >= self.minimum_score:
                results.append(MatterMatch(matter_id=matter.id, score=min(score, 1.0), reasons=tuple(reasons)))
        return sorted(results, key=lambda item: item.score, reverse=True)

    def best_match(self, text: str, matters: list[Matter]) -> MatterMatch | None:
        matches = self.match(text, matters)
        return matches[0] if matches else None
