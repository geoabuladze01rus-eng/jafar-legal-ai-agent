from datetime import datetime, timedelta, timezone

from jafar.editorial_calendar import EditorialItem, EditorialStatus
from jafar.editorial_pipeline import NewsEvent, ContentFormat, select_ideas


def test_official_recent_event_can_be_breaking():
    event = NewsEvent(
        title="Важное судебное решение",
        summary="summary",
        source_url="https://example.test/source",
        published_at=datetime.now(timezone.utc),
        official=True,
        legal_relevance=1.0,
        public_interest=1.0,
        novelty=1.0,
    )
    ideas = select_ideas([event])
    assert ideas[0].format == ContentFormat.BREAKING


def test_old_low_relevance_event_is_not_breaking():
    event = NewsEvent(
        title="Старое событие",
        summary="summary",
        source_url="https://example.test/source",
        published_at=datetime.now(timezone.utc) - timedelta(days=10),
        legal_relevance=0.1,
        public_interest=0.1,
        novelty=0.1,
    )
    ideas = select_ideas([event])
    assert ideas[0].format == ContentFormat.EXPLAINER


def test_item_requires_approval_before_schedule():
    item = EditorialItem("1", "Тема", "explainer", datetime.now(timezone.utc), EditorialStatus.DRAFT)
    item.approve()
    assert item.status == EditorialStatus.APPROVED
    item.schedule()
    assert item.status == EditorialStatus.SCHEDULED
