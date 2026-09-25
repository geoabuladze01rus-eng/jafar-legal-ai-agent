from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol, Sequence

from pydantic import BaseModel, Field, model_validator


class AnalyticsUnavailable(RuntimeError):
    pass


class PostMetrics(BaseModel):
    publication_id: str
    telegram_message_id: int | None = None
    title: str | None = None
    views: int | None = Field(default=None, ge=0)
    forwards: int | None = Field(default=None, ge=0)
    reactions: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    subscriber_count_at_publish: int | None = Field(default=None, ge=0)
    client_inquiries: int | None = Field(default=None, ge=0)

    @property
    def err_percent(self) -> float | None:
        if self.views is None or not self.subscriber_count_at_publish:
            return None
        return self.views / self.subscriber_count_at_publish * 100

    @property
    def engagement_rate_percent(self) -> float | None:
        if not self.views:
            return None
        known = [self.forwards, self.reactions, self.comments]
        if all(value is None for value in known):
            return None
        interactions = sum(value or 0 for value in known)
        return interactions / self.views * 100


class WeeklyAnalyticsDataset(BaseModel):
    start_date: date
    end_date: date
    subscriber_count_start: int | None = Field(default=None, ge=0)
    subscriber_count_end: int | None = Field(default=None, ge=0)
    posts: list[PostMetrics] = Field(default_factory=list)
    source_name: str

    @model_validator(mode="after")
    def validate_range(self) -> WeeklyAnalyticsDataset:
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self

    @property
    def subscriber_delta(self) -> int | None:
        if self.subscriber_count_start is None or self.subscriber_count_end is None:
            return None
        return self.subscriber_count_end - self.subscriber_count_start


class TelegramAnalyticsAdapter(Protocol):
    name: str

    def fetch_week(self, *, start_date: date, end_date: date) -> WeeklyAnalyticsDataset: ...


@dataclass(slots=True)
class ManualImportAdapter:
    dataset: WeeklyAnalyticsDataset
    name: str = "manual_import"

    def fetch_week(self, *, start_date: date, end_date: date) -> WeeklyAnalyticsDataset:
        if self.dataset.start_date != start_date or self.dataset.end_date != end_date:
            raise AnalyticsUnavailable("manual dataset does not cover requested period")
        return self.dataset


@dataclass(slots=True)
class DisabledAnalyticsAdapter:
    name: str
    reason: str

    def fetch_week(self, *, start_date: date, end_date: date) -> WeeklyAnalyticsDataset:
        del start_date, end_date
        raise AnalyticsUnavailable(f"{self.name} disabled: {self.reason}")


class WeeklyObservation(BaseModel):
    fact: str
    meaning: str
    why_hypothesis: str
    next_action: str


class WeeklyAnalyticsReport(BaseModel):
    start_date: date
    end_date: date
    source_name: str
    observations: list[WeeklyObservation]
    missing_metrics: list[str] = Field(default_factory=list)


class WeeklyAnalyticsAnalyzer:
    """Turns supplied metrics into transparent observations; never fabricates missing data."""

    def analyze(self, dataset: WeeklyAnalyticsDataset) -> WeeklyAnalyticsReport:
        observations: list[WeeklyObservation] = []
        missing: set[str] = set()

        delta = dataset.subscriber_delta
        if delta is None:
            missing.add("subscriber_delta")
        else:
            observations.append(
                WeeklyObservation(
                    fact=f"Изменение подписчиков за период: {delta:+d}.",
                    meaning=(
                        "Аудитория выросла." if delta > 0 else "Аудитория сократилась или не выросла."
                    ),
                    why_hypothesis=(
                        "Причину нельзя установить только по числу подписчиков; нужно сопоставить "
                        "публикации, рекламные источники и отписки."
                    ),
                    next_action="Сопоставить прирост с датами постов, рекламы и обращений.",
                )
            )

        posts_with_views = [post for post in dataset.posts if post.views is not None]
        if posts_with_views:
            best = max(posts_with_views, key=lambda post: post.views or 0)
            observations.append(
                WeeklyObservation(
                    fact=f"Максимальный охват: {best.views} у публикации {best.publication_id}.",
                    meaning="Эта публикация лучше остальных привлекла внимание по доступной метрике views.",
                    why_hypothesis=(
                        "Это корреляция, а не доказанная причина; проверь тему, hook, время публикации "
                        "и пересылки относительно других постов."
                    ),
                    next_action="Разобрать механику поста и протестировать её на новой теме без копирования текста.",
                )
            )
        else:
            missing.add("views")

        posts_with_forwards = [post for post in dataset.posts if post.forwards is not None]
        if posts_with_forwards:
            most_shared = max(posts_with_forwards, key=lambda post: post.forwards or 0)
            observations.append(
                WeeklyObservation(
                    fact=(
                        f"Больше всего пересылок: {most_shared.forwards} у публикации "
                        f"{most_shared.publication_id}."
                    ),
                    meaning="Пост имеет лучший подтверждённый потенциал распространения внутри выборки.",
                    why_hypothesis="Вероятная причина — практическая или дискуссионная ценность; это нужно проверить по содержанию.",
                    next_action="Добавить близкую по механике тему в резерв контент-плана.",
                )
            )
        else:
            missing.add("forwards")

        if dataset.posts and all(post.client_inquiries is None for post in dataset.posts):
            missing.add("client_inquiries")

        return WeeklyAnalyticsReport(
            start_date=dataset.start_date,
            end_date=dataset.end_date,
            source_name=dataset.source_name,
            observations=observations,
            missing_metrics=sorted(missing),
        )


def merge_datasets(datasets: Sequence[WeeklyAnalyticsDataset]) -> WeeklyAnalyticsDataset:
    if not datasets:
        raise ValueError("at least one dataset is required")
    first = datasets[0]
    if any(item.start_date != first.start_date or item.end_date != first.end_date for item in datasets):
        raise ValueError("analytics datasets must cover the same period")

    posts: dict[str, PostMetrics] = {}
    for dataset in datasets:
        for post in dataset.posts:
            existing = posts.get(post.publication_id)
            if existing is None:
                posts[post.publication_id] = post
                continue
            merged = existing.model_dump()
            incoming = post.model_dump()
            for key, value in incoming.items():
                if value is not None:
                    merged[key] = value
            posts[post.publication_id] = PostMetrics.model_validate(merged)

    start_count = next(
        (item.subscriber_count_start for item in datasets if item.subscriber_count_start is not None),
        None,
    )
    end_count = next(
        (item.subscriber_count_end for item in datasets if item.subscriber_count_end is not None),
        None,
    )
    return WeeklyAnalyticsDataset(
        start_date=first.start_date,
        end_date=first.end_date,
        subscriber_count_start=start_count,
        subscriber_count_end=end_count,
        posts=list(posts.values()),
        source_name=" + ".join(item.source_name for item in datasets),
    )
