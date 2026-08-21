from datetime import date

from jafar.analytics import PostMetrics
from jafar.daily_report import build_daily_report


def test_daily_report_aggregates_metrics():
    report = build_daily_report(
        [
            PostMetrics("a", views=1000, reactions=50, forwards=10, new_subscribers=5),
            PostMetrics("b", views=500, reactions=10, forwards=2, new_subscribers=1),
        ],
        report_date=date(2026, 8, 21),
    )
    assert report.total_views == 1500
    assert report.total_new_subscribers == 6
    assert report.best_post_id == "a"
