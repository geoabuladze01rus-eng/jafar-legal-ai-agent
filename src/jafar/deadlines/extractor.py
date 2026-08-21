from dataclasses import dataclass
from datetime import date
import re


@dataclass(frozen=True)
class DeadlineProposal:
    source_id: str
    due_date: date
    basis: str
    confidence: float
    requires_approval: bool = True


_DATE_PATTERNS = (
    re.compile(r"(?:до|не позднее)\s+(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})", re.I),
    re.compile(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})"),
)


def extract_deadlines(text: str, source_id: str) -> list[DeadlineProposal]:
    proposals: list[DeadlineProposal] = []
    for pattern in _DATE_PATTERNS:
        for match in pattern.finditer(text):
            day, month, year = map(int, match.groups())
            if year < 100:
                year += 2000
            try:
                due = date(year, month, day)
            except ValueError:
                continue
            basis = match.group(0)
            confidence = 0.92 if re.match(r"(?:до|не позднее)", basis, re.I) else 0.65
            proposals.append(DeadlineProposal(source_id, due, basis, confidence))
    return list(dict.fromkeys(proposals))
