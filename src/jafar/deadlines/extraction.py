import re
from datetime import datetime

from jafar.deadlines.models import DeadlineCandidate

_DATE_RE = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b")


def extract_explicit_dates(text: str, *, source_document_id: str | None = None, source_chunk_id: str | None = None) -> list[DeadlineCandidate]:
    candidates: list[DeadlineCandidate] = []
    for match in _DATE_RE.finditer(text):
        day, month, year = map(int, match.groups())
        try:
            due_at = datetime(year, month, day)
        except ValueError:
            continue
        window_start = max(0, match.start() - 100)
        window_end = min(len(text), match.end() + 100)
        context = text[window_start:window_end].replace("\n", " ")
        if re.search(r"срок|до |не позднее|представить|обжалован|явк", context, re.I):
            candidates.append(
                DeadlineCandidate(
                    title=f"Проверить срок: {match.group(0)}",
                    due_at=due_at,
                    source_document_id=source_document_id,
                    source_chunk_id=source_chunk_id,
                    confidence=0.75,
                    reason=context,
                )
            )
    return candidates
