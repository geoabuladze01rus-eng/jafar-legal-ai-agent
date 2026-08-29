from datetime import date, datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field

from .domains import DocumentTask, MatterType


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class Deadline(BaseModel):
    title: str = Field(min_length=1, max_length=1000)
    due_date: date | None = None
    source_text: str | None = Field(default=None, max_length=20_000)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class LegalIssue(BaseModel):
    title: str = Field(min_length=1, max_length=1000)
    description: str = Field(max_length=20_000)
    risk: RiskLevel = RiskLevel.UNKNOWN
    source_text: str | None = Field(default=None, max_length=20_000)


class LegalAnalysis(BaseModel):
    task: DocumentTask
    matter_type: MatterType
    summary: str = Field(max_length=50_000)
    issues: list[LegalIssue] = Field(default_factory=list, max_length=500)
    deadlines: list[Deadline] = Field(default_factory=list, max_length=500)
    key_facts: list[str] = Field(default_factory=list, max_length=1000)
    missing_information: list[str] = Field(default_factory=list, max_length=1000)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Matter(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    matter_type: MatterType
    client_name: str | None = Field(default=None, max_length=500)
    opposing_party: str | None = Field(default=None, max_length=500)
    court_or_authority: str | None = Field(default=None, max_length=1000)
    case_number: str | None = Field(default=None, max_length=500)
    status: str = Field(default="active", min_length=1, max_length=100)
    deadlines: list[Deadline] = Field(default_factory=list, max_length=1000)
    created_at: datetime
    updated_at: datetime


class MatterEvent(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    matter_id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=1000)
    event_date: datetime
    description: str | None = Field(default=None, max_length=20_000)
    source_document: str | None = Field(default=None, max_length=2000)
    document_fingerprint: str | None = Field(default=None, max_length=200)
    created_at: datetime


class AnalysisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200_000)
    task: DocumentTask = DocumentTask.LEGAL_ANALYSIS
    matter_type: MatterType = MatterType.GENERAL
    matter_id: str | None = Field(default=None, max_length=200)


class AnalysisResponse(BaseModel):
    analysis: LegalAnalysis
    matter_id: str | None = Field(default=None, max_length=200)
    persisted: bool = False
    requires_approval_to_persist: bool = True
