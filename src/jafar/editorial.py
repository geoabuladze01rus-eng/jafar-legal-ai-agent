from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class PublicationStatus(StrEnum):
    DRAFT = "draft"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"


class EditorialRisk(StrEnum):
    LOW = "low"
    REVIEW = "review"
    HIGH = "high"


class EditorialPost(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=4096)
    scheduled_at: str | None = None
    status: PublicationStatus = PublicationStatus.DRAFT
    risk: EditorialRisk = EditorialRisk.REVIEW
    source_urls: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    requires_human_approval: bool = True


HIGH_RISK_RULES = (
    "personal_data",
    "unverified_accusation",
    "individual_legal_advice",
    "confidential_case_material",
    "sensitive_criminal_case",
)


def requires_human_review(post: EditorialPost) -> bool:
    """Keep consequential or legally sensitive publications behind an approval gate."""
    return post.requires_human_approval or post.risk in {
        EditorialRisk.REVIEW,
        EditorialRisk.HIGH,
    }
