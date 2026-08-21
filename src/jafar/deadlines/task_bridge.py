from dataclasses import dataclass
from datetime import datetime, timezone

from jafar.deadlines.extractor import DeadlineProposal
from jafar.tasks.models import TaskProposal


@dataclass(frozen=True)
class DeadlineTaskProposal:
    deadline: DeadlineProposal
    task: TaskProposal


def build_task_proposal(deadline: DeadlineProposal, matter_id: str, title: str, source_id: str) -> DeadlineTaskProposal:
    due_at = datetime.combine(deadline.due_date, datetime.min.time(), tzinfo=timezone.utc)
    task = TaskProposal(
        task_id=f"proposal-{source_id}-{deadline.due_date.isoformat()}",
        matter_id=matter_id,
        title=title,
        description=f"Срок извлечён из источника: {deadline.basis}",
        due_at=due_at,
        source_id=source_id,
        confidence=deadline.confidence,
        requires_approval=True,
    )
    return DeadlineTaskProposal(deadline, task)
