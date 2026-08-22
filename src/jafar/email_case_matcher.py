from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class CaseCandidate:
    case_id: str
    score: float
    reasons: tuple[str, ...]


class EmailCaseMatcher:
    """Ranks existing cases against an email without silently attaching it."""

    def match(self, *, subject: str, body: str, cases: Iterable[dict[str, Any]]) -> list[CaseCandidate]:
        text = f"{subject}\n{body}".lower()
        tokens = set(re.findall(r"[a-zа-яё0-9-]{4,}", text))
        candidates: list[CaseCandidate] = []
        for case in cases:
            reasons: list[str] = []
            score = 0.0
            case_id = str(case["case_id"])
            for key in ("case_number", "inn", "ogrn"):
                value = str(case.get(key) or "").lower()
                if value and value in text:
                    score += 0.7
                    reasons.append(f"exact:{key}")
            for value in case.get("keywords", []):
                if str(value).lower() in tokens:
                    score += 0.1
                    reasons.append(f"keyword:{value}")
            if score:
                candidates.append(CaseCandidate(case_id, min(score, 1.0), tuple(reasons)))
        return sorted(candidates, key=lambda item: item.score, reverse=True)
