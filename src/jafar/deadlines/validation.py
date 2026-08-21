from dataclasses import dataclass
from datetime import datetime, timezone

from jafar.deadlines.models import DeadlineCandidate


@dataclass(frozen=True)
class DeadlineReview:
    candidate: DeadlineCandidate
    confirmed: bool
    warnings: list[str]


def review_deadline(candidate: DeadlineCandidate) -> DeadlineReview:
    warnings: list[str] = []
    confirmed = False

    if candidate.due_at is None:
        warnings.append("Дата не определена; требуется ручная проверка.")
    elif candidate.due_at.tzinfo is None:
        warnings.append("Время не содержит часовой пояс; требуется нормализация.")
    elif candidate.due_at <= datetime.now(timezone.utc):
        warnings.append("Дата уже наступила или истекла; требуется проверка процессуального контекста.")

    if not candidate.source_document_id:
        warnings.append("Отсутствует источник-документ.")
    if candidate.confidence < 0.9:
        warnings.append("Уверенность ниже порога автоматического подтверждения.")

    return DeadlineReview(candidate=candidate, confirmed=confirmed, warnings=warnings)
