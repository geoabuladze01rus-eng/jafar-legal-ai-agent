from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CalendarCaseMatch:
    event_id: str
    case_id: str
    confidence: float
    reasons: tuple[str, ...]


class CalendarIntelligence:
    """Matches calendar events to cases; never mutates the calendar automatically."""

    def match(self, events: Iterable[dict[str, Any]], cases: Iterable[dict[str, Any]]) -> list[CalendarCaseMatch]:
        cases_list = list(cases)
        result: list[CalendarCaseMatch] = []
        for event in events:
            text = f"{event.get('subject', '')} {event.get('body', '')}".lower()
            for case in cases_list:
                score = 0.0
                reasons: list[str] = []
                for key in ("case_number", "inn", "ogrn"):
                    value = str(case.get(key) or "").lower()
                    if value and value in text:
                        score = min(1.0, score + 0.8)
                        reasons.append(f"exact:{key}")
                for keyword in case.get("keywords", []):
                    if str(keyword).lower() in text:
                        score = min(1.0, score + 0.1)
                        reasons.append(f"keyword:{keyword}")
                if score:
                    result.append(CalendarCaseMatch(str(event.get("event_id", "")), str(case["case_id"]), score, tuple(reasons)))
        return sorted(result, key=lambda item: item.confidence, reverse=True)

    @staticmethod
    def deadline_candidates(event: dict[str, Any]) -> list[dict[str, Any]]:
        text = f"{event.get('subject', '')} {event.get('body', '')}".lower()
        terms = ("срок", "обжалован", "заседан", "явка", "документ")
        return [{"event_id": event.get("event_id"), "kind": "legal_deadline_candidate", "matched_terms": [term for term in terms if term in text]}] if any(term in text for term in terms) else []
