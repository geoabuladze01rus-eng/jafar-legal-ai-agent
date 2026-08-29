from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TelegramCaseCandidate:
    case_id: str
    score: float
    reasons: tuple[str, ...]


class TelegramCaseMatcher:
    """Ranks case candidates; it never attaches a Telegram message automatically."""

    def match(self, *, message: str, cases: Iterable[dict[str, Any]]) -> list[TelegramCaseCandidate]:
        text = message.lower()
        tokens = set(re.findall(r"[a-zа-яё0-9-]{4,}", text))
        result: list[TelegramCaseCandidate] = []
        for case in cases:
            score = 0.0
            reasons: list[str] = []
            for field in ("case_number", "inn", "ogrn"):
                value = str(case.get(field) or "").lower()
                if value and value in text:
                    score += 0.75
                    reasons.append(f"exact:{field}")
            for keyword in case.get("keywords", []):
                if str(keyword).lower() in tokens:
                    score += 0.1
                    reasons.append(f"keyword:{keyword}")
            if score:
                result.append(TelegramCaseCandidate(str(case["case_id"]), min(score, 1.0), tuple(reasons)))
        return sorted(result, key=lambda item: item.score, reverse=True)
