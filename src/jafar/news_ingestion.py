from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .news_dedup import SeenNews, fingerprint


@dataclass(frozen=True)
class IncomingNews:
    title: str
    summary: str
    source_url: str
    published_at: datetime
    official: bool = False


class NewsIngestion:
    def __init__(self) -> None:
        self.seen = SeenNews()

    def accept(self, item: IncomingNews) -> IncomingNews | None:
        fp = fingerprint(item.title, item.source_url)
        return item if self.seen.add_if_new(fp) else None
