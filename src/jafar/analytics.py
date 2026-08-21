from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PostMetrics:
    post_id: str
    views: int
    reactions: int = 0
    comments: int = 0
    forwards: int = 0
    new_subscribers: int = 0

    @property
    def engagement_rate(self) -> float:
        if self.views <= 0:
            return 0.0
        return (self.reactions + self.comments + self.forwards) / self.views

    @property
    def conversion_rate(self) -> float:
        if self.views <= 0:
            return 0.0
        return self.new_subscribers / self.views


def rank_posts(items: list[PostMetrics]) -> list[PostMetrics]:
    return sorted(
        items,
        key=lambda item: (item.engagement_rate, item.conversion_rate),
        reverse=True,
    )
