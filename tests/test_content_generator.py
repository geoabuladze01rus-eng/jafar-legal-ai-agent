from datetime import datetime, timezone

from jafar.content_generator import build_draft
from jafar.editorial_calendar import EditorialItem, EditorialStatus


def test_generated_draft_requires_review():
    item = EditorialItem(
        id="1",
        title="Тестовая публикация",
        format="explainer",
        planned_at=datetime.now(timezone.utc),
        status=EditorialStatus.DRAFT,
    )
    draft = build_draft(item, source_facts="Факт из проверенного источника.")
    assert draft.requires_review is True
    assert "Факт из проверенного источника" in draft.body
    assert "❓" in draft.body
