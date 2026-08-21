from dataclasses import replace

from jafar.inbox.queue import InMemoryInboxQueue, InboxAnalysisJob, JobStatus


class InboxWorker:
    def __init__(self, queue: InMemoryInboxQueue) -> None:
        self.queue = queue

    def process_next(self, handler) -> InboxAnalysisJob | None:
        pending = self.queue.pending()
        if not pending:
            return None

        job = pending[0]
        processing = replace(job, status=JobStatus.PROCESSING, attempts=job.attempts + 1)
        self.queue.enqueue(processing)
        try:
            handler(processing)
        except Exception as exc:
            failed = replace(processing, status=JobStatus.FAILED, error=str(exc))
            self.queue.enqueue(failed)
            return failed

        completed = replace(processing, status=JobStatus.COMPLETED)
        self.queue.enqueue(completed)
        return completed
