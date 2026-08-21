from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .analytics import PostMetrics, rank_posts


@dataclass(frozen=True)
class DailyReport:
    report_date: date
    total_views: int
    total_new_subscribers: int
    average_engagement_rate: float
    best_post_id: str | None
    recommendations: tuple[str, ...]


def build_daily_report(items: list[PostMetrics], report_date: date | None = None) -> DailyReport:
    today = report_date or date.today()
    if not items:
        return DailyReport(today, 0, 0, 0.0, None, ("Недостаточно данных для рекомендаций.",))

    ranked = rank_posts(items)
    views = sum(item.views for item in items)
    subscribers = sum(item.new_subscribers for item in items)
    average_er = sum(item.engagement_rate for item in items) / len(items)

    recommendations: list[str] = []
    if average_er < 0.03:
        recommendations.append("Тестировать более вовлекающие заголовки и вопросы аудитории.")
    if subscribers == 0:
        recommendations.append("Добавить больше материалов с явным призывом подписаться или переслать пост.")
    if ranked and ranked[0].forwards > ranked[0].reactions:
        recommendations.append("Увеличить долю материалов, которые удобно пересылать другим.")

    return DailyReport(
        report_date=today,
        total_views=views,
        total_new_subscribers=subscribers,
        average_engagement_rate=average_er,
        best_post_id=ranked[0].post_id,
        recommendations=tuple(recommendations),
    )
