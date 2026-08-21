from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class EditorialStatus(StrEnum):
    IDEA = "idea"
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"


@dataclass
class EditorialItem:
    id: str
    title: str
    format: str
    planned_at: datetime
    status: EditorialStatus = EditorialStatus.IDEA
    body: str | None = None
    source_url: str | None = None

    def approve(self) -> None:
        if self.status not in {EditorialStatus.DRAFT, EditorialStatus.REVIEW}:
            raise ValueError("Only draft/review items can be approved")
        self.status = EditorialStatus.APPROVED

    def schedule(self) -> None:
        if self.status != EditorialStatus.APPROVED:
            raise ValueError("Only approved items can be scheduled")
        self.status = EditorialStatus.SCHEDULED
