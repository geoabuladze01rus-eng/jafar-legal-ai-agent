from __future__ import annotations

from dataclasses import dataclass

from .precedent_freshness import FreshnessStatus, PrecedentFreshnessReport


@dataclass(frozen=True, slots=True)
class PrecedentReleaseDecision:
    ready: bool
    blocked_authority_ids: tuple[str, ...]
    reasons: tuple[str, ...]


class PrecedentReleasePolicy:
    """Prevent unresolved precedent conflicts from silently entering final legal drafting."""

    BLOCKING = {
        FreshnessStatus.SUPERSEDED,
        FreshnessStatus.CONFLICTING,
        FreshnessStatus.REVIEW_REQUIRED,
    }

    def decide(self, report: PrecedentFreshnessReport) -> PrecedentReleaseDecision:
        blocked = tuple(
            item.precedent.authority_id
            for item in report.items
            if item.status in self.BLOCKING
        )
        reasons: list[str] = []
        if blocked:
            reasons.append(
                "Есть конфликтующие, преодолённые или неразрешённые позиции; требуется проверка treatment перед использованием."
            )
        if report.conflicts:
            reasons.append("Обнаружены подтверждённые конфликтующие precedent relations.")
        return PrecedentReleaseDecision(
            ready=not blocked and not report.requires_human_review,
            blocked_authority_ids=blocked,
            reasons=tuple(reasons),
        )
