from dataclasses import dataclass
from typing import Callable, Protocol

from jafar.inbox.queue import InboxAnalysisJob, JobStatus


class LegalAnalysisHandler(Protocol):
    def __call__(self, job: InboxAnalysisJob) -> None: ...


@dataclass(frozen=True)
class PipelineOutcome:
    job_id: str
    status: JobStatus
    analysis_started: bool
    notification_requested: bool


class AutonomousInboxPipeline:
    """Orchestrates triaged legal-mail jobs without sending external messages itself."""

    def __init__(
        self,
        analyze: LegalAnalysisHandler,
        notify: Callable[[InboxAnalysisJob], None],
    ) -> None:
        self.analyze = analyze
        self.notify = notify

    def run(self, job: InboxAnalysisJob) -> PipelineOutcome:
        if not job.classification.needs_analysis:
            return PipelineOutcome(job.job_id, job.status, False, False)

        self.analyze(job)
        self.notify(job)
        return PipelineOutcome(job.job_id, JobStatus.COMPLETED, True, True)
