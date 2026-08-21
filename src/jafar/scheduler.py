from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ScheduledPost:
    post_id: str
    text: str
    publish_at: datetime
    approved: bool = False

    def is_due(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        return self.approved and current >= self.publish_at


class PublicationQueue:
    def __init__(self) -> None:
        self._items: list[ScheduledPost] = []

    def add(self, post: ScheduledPost) -> None:
        self._items.append(post)
        self._items.sort(key=lambda item: item.publish_at)

    def due(self, now: datetime | None = None) -> list[ScheduledPost]:
        return [item for item in self._items if item.is_due(now)]
