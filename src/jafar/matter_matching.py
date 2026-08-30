from __future__ import annotations

import re
from dataclasses import dataclass

from .legal_models import Matter


@dataclass(frozen=True)
class MatterCandidate:
    matter_id: str
    score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class MatterMatch:
    matter_id: str
    score: float
    reasons: tuple[str, ...]
    candidates: tuple[MatterCandidate, ...] = ()


class MatterMatcher:
    """Conservative document-to-matter matcher.

    The legacy inbox scoring is preserved, but a document is only auto-linked
    when the top candidate is strong enough and clearly separated from the
    runner-up. Ambiguous or weak matches return None.
    """

    def __init__(self, min_score: float = 0.75, min_margin: float = 0.10) -> None:
        self.min_score = min_score
        self.min_margin = min_margin

    @staticmethod
    def _terms(value: str) -> set[str]:
        return set(re.findall(r"[а-яёa-z0-9]{4,}", value.lower()))

    def candidates(self, text: str, matters: list[Matter]) -> list[MatterCandidate]:
        normalized = text.lower()
        results: list[MatterCandidate] = []
        for matter in matters:
            score = 0.0
            reasons: list[str] = []

            case_number = (matter.case_number or "").strip().lower()
            if case_number and case_number in normalized:
                score += 0.75
                reasons.append("совпадает номер дела")

            title_terms = self._terms(matter.title)
            matched_title = [term for term in title_terms if term in normalized]
            score += min(0.15, 0.03 * len(matched_title))
            if matched_title:
                reasons.append("совпадают слова из названия дела")

            party_terms = self._terms(
                " ".join(
                    value
                    for value in (
                        matter.client_name,
                        matter.opposing_party,
                        matter.court_or_authority,
                    )
                    if value
                )
            )
            if any(term in normalized for term in party_terms):
                score += 0.10
                reasons.append("найден участник или орган по делу")

            if score > 0:
                results.append(
                    MatterCandidate(
                        matter_id=matter.id,
                        score=min(score, 0.99),
                        reasons=tuple(reasons),
                    )
                )
        return sorted(results, key=lambda item: item.score, reverse=True)

    def best_match(self, text: str, matters: list[Matter]) -> MatterMatch | None:
        candidates = self.candidates(text, matters)
        if not candidates:
            return None

        top = candidates[0]
        runner_up = candidates[1] if len(candidates) > 1 else None
        if top.score < self.min_score:
            return None
        if runner_up and (top.score - runner_up.score) < self.min_margin:
            return None

        return MatterMatch(
            matter_id=top.matter_id,
            score=top.score,
            reasons=top.reasons,
            candidates=tuple(candidates[:5]),
        )
