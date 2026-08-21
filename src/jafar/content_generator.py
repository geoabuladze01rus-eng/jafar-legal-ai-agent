from __future__ import annotations

from dataclasses import dataclass

from .editorial_calendar import EditorialItem


@dataclass(frozen=True)
class Draft:
    title: str
    body: str
    requires_review: bool


def build_draft(item: EditorialItem, *, source_facts: str) -> Draft:
    """Build a conservative draft from supplied facts only.

    This layer intentionally does not invent legal conclusions or facts. The
    resulting item remains in review until explicitly approved.
    """
    body = (
        f"{source_facts.strip()}\n\n"
        "💎 ИТОГ: проверяйте обстоятельства конкретной ситуации и первичные источники.\n\n"
        "❓ Что вы думаете об этой ситуации?"
    )
    return Draft(title=item.title, body=body, requires_review=True)
