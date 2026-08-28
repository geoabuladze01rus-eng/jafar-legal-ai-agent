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
    title: str
    due_date: date | None = None
    source_text: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class LegalIssue(BaseModel):
    title: str
    description: str
    risk: RiskLevel = RiskLevel.UNKNOWN
    source_text: str | None = None


class LegalAnalysis(BaseModel):
    task: DocumentTask
    matter_type: MatterType
    summary: str
    issues: list[LegalIssue] = Field(default_factory=list)
    deadlines: list[Deadline] = Field(default_factory=list)
    key_facts: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Matter(BaseModel):
    id: str
    title: str
    matter_type: MatterType
    client_name: str | None = None
    opposing_party: str | None = None
    court_or_authority: str | None = None
    case_number: str | None = None
    status: str = "active"
    deadlines: list[Deadline] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class MatterEvent(BaseModel):
    id: str
    matter_id: str
    title: str
    event_date: datetime
    description: str | None = None
    source_document: str | None = None
    document_fingerprint: str | None = None
    created_at: datetime


class AnalysisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200_000)
    task: DocumentTask = DocumentTask.LEGAL_ANALYSIS
    matter_type: MatterType = MatterType.GENERAL
    matter_id: str | None = None


class AnalysisResponse(BaseModel):
    analysis: LegalAnalysis
    matter_id: str | None = None
    persisted: bool = False
    requires_approval_to_persist: bool = True
