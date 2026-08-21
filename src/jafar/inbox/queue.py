from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from jafar.inbox.classifier import Classification


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


@dataclass(frozen=True)
class InboxAnalysisJob:
    job_id: str
    message_id: str
    classification: Classification
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = datetime.now(timezone.utc)
    attempts: int = 0
    error: str | None = None


class InMemoryInboxQueue:
    def __init__(self) -> None:
        self._jobs: dict[str, InboxAnalysisJob] = {}

    def enqueue(self, job: InboxAnalysisJob) -> None:
        self._jobs[job.job_id] = job

    def get(self, job_id: str) -> InboxAnalysisJob | None:
        return self._jobs.get(job_id)

    def pending(self) -> list[InboxAnalysisJob]:
        return [job for job in self._jobs.values() if job.status == JobStatus.QUEUED]
