import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MatterCandidate:
    matter_id: str
    score: float
    reasons: tuple[str, ...]


def match_matter(
    subject: str,
    body: str,
    sender: str,
    matters: list[dict[str, str]],
) -> list[MatterCandidate]:
    text = f"{subject} {body} {sender}".lower()
    results: list[MatterCandidate] = []
    for matter in matters:
        score = 0.0
        reasons: list[str] = []
        case_number = matter.get("case_number", "").strip().lower()
        title = matter.get("title", "").lower()
        parties = matter.get("parties", "").lower()
        if case_number and case_number in text:
            score += 0.75
            reasons.append("совпадает номер дела")
        title_terms = {x for x in re.findall(r"[а-яёa-z0-9]{4,}", title) if x}
        matched_title = [term for term in title_terms if term in text]
        score += min(0.15, 0.03 * len(matched_title))
        if matched_title:
            reasons.append("совпадают слова из названия дела")
        party_terms = {x for x in re.findall(r"[а-яёa-z0-9]{4,}", parties) if x}
        if any(term in text for term in party_terms):
            score += 0.10
            reasons.append("найден участник дела")
        if score > 0:
            results.append(MatterCandidate(matter["matter_id"], min(score, 0.99), tuple(reasons)))
    return sorted(results, key=lambda item: item.score, reverse=True)
