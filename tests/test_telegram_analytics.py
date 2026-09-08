from __future__ import annotations

from datetime import date

import pytest

from jafar.telegram_analytics import (
    AnalyticsUnavailable,
    ManualImportAdapter,
    PostMetrics,
    WeeklyAnalyticsAnalyzer,
    WeeklyAnalyticsDataset,
    merge_datasets,
)


def _week(**overrides):
    data = {
        "start_date": date(2026, 9, 1),
        "end_date": date(2026, 9, 7),
        "source_name": "telegram_export",
        "posts": [],
    }
    data.update(overrides)
    return WeeklyAnalyticsDataset(**data)


def test_unknown_metrics_are_reported_missing_not_zero() -> None:
    dataset = _week(posts=[PostMetrics(publication_id="tg_1")])

    report = WeeklyAnalyticsAnalyzer().analyze(dataset)

    assert report.observations == []
    assert report.missing_metrics == ["client_inquiries", "forwards", "subscriber_delta", "views"]


def test_rates_only_exist_when_denominators_and_inputs_are_known() -> None:
    unknown = PostMetrics(publication_id="tg_unknown", views=None, subscriber_count_at_publish=1000)
    zero_views = PostMetrics(publication_id="tg_zero", views=0, forwards=0, reactions=0, comments=0)
    known = PostMetrics(
        publication_id="tg_known",
        views=500,
        forwards=10,
        reactions=20,
        comments=5,
        subscriber_count_at_publish=1000,
    )

    assert unknown.err_percent is None
    assert unknown.engagement_rate_percent is None
    assert zero_views.engagement_rate_percent is None
    assert known.err_percent == 50.0
    assert known.engagement_rate_percent == 7.0


def test_analyzer_uses_only_supplied_metrics_for_best_posts() -> None:
    dataset = _week(
        subscriber_count_start=1000,
        subscriber_count_end=1040,
        posts=[
            PostMetrics(publication_id="tg_a", views=900, forwards=4, client_inquiries=1),
            PostMetrics(publication_id="tg_b", views=700, forwards=12, client_inquiries=2),
        ],
    )

    report = WeeklyAnalyticsAnalyzer().analyze(dataset)
    facts = [item.fact for item in report.observations]

    assert "Изменение подписчиков за период: +40." in facts
    assert "Максимальный охват: 900 у публикации tg_a." in facts
    assert "Больше всего пересылок: 12 у публикации tg_b." in facts
    assert report.missing_metrics == []


def test_merge_datasets_combines_partial_metrics_without_inventing_values() -> None:
    telegram = _week(
        source_name="telegram",
        subscriber_count_start=1000,
        posts=[PostMetrics(publication_id="tg_a", views=500, forwards=None)],
    )
    inquiries = _week(
        source_name="crm",
        subscriber_count_end=1035,
        posts=[PostMetrics(publication_id="tg_a", client_inquiries=3)],
    )

    merged = merge_datasets([telegram, inquiries])

    assert merged.subscriber_count_start == 1000
    assert merged.subscriber_count_end == 1035
    assert merged.source_name == "telegram + crm"
    assert len(merged.posts) == 1
    post = merged.posts[0]
    assert post.views == 500
    assert post.client_inquiries == 3
    assert post.forwards is None


def test_merge_rejects_different_periods() -> None:
    first = _week()
    second = WeeklyAnalyticsDataset(
        start_date=date(2026, 9, 2),
        end_date=date(2026, 9, 8),
        source_name="other",
    )

    with pytest.raises(ValueError, match="same period"):
        merge_datasets([first, second])


def test_manual_import_adapter_fails_closed_for_wrong_period() -> None:
    adapter = ManualImportAdapter(_week())

    with pytest.raises(AnalyticsUnavailable, match="does not cover"):
        adapter.fetch_week(start_date=date(2026, 9, 2), end_date=date(2026, 9, 8))
