from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .case_theory import TheoryStatus
from .theory_views import DualTheoryReport, TheoryViewItem


class AttackSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AttackSignalKind(StrEnum):
    CONTRADICTED = "contradicted"
    REVIEW_REQUIRED = "review_required"
    UNSUPPORTED = "unsupported"
    SINGLE_SOURCE = "single_source"
    SINGLE_DOCUMENT_FINGERPRINT = "single_document_fingerprint"
    SINGLE_ACTOR = "single_actor"
    DEFENSE_COUNTERTHESIS = "defense_counterthesis"


@dataclass(frozen=True, slots=True)
class AttackSurfaceItem:
    issue_id: str
    topic: str
    statement: str
    score: int
    severity: AttackSeverity
    signals: tuple[AttackSignalKind, ...]
    reasons: tuple[str, ...]
    prosecution_sources: tuple[dict[str, Any], ...]
    defense_sources: tuple[dict[str, Any], ...]
    recommended_focus: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AttackSurfaceReport:
    items: tuple[AttackSurfaceItem, ...]
    highest_priority_issue_ids: tuple[str, ...]
    requires_human_review: bool


class ProsecutionAttackSurfaceEngine:
    """Rank prosecution theses by review priority, not by ultimate legal validity."""

    def build(self, report: DualTheoryReport) -> AttackSurfaceReport:
        defense_by_topic: dict[str, list[TheoryViewItem]] = {}
        for item in report.defense:
            defense_by_topic.setdefault(item.topic, []).append(item)

        ranked: list[AttackSurfaceItem] = []
        for item in report.prosecution:
            score = 0
            signals: list[AttackSignalKind] = []
            reasons: list[str] = []
            focus: list[str] = []
            defense_items = defense_by_topic.get(item.topic, [])

            if item.status == TheoryStatus.CONTRADICTED:
                score += 35
                signals.append(AttackSignalKind.CONTRADICTED)
                reasons.append("Тезис уже связан с поддержанным источниками противоречием.")
                focus.append(
                    "Сопоставить противоречащие источники и подготовить вопросы по расхождениям."
                )
            elif item.status == TheoryStatus.REVIEW_REQUIRED:
                score += 30
                signals.append(AttackSignalKind.REVIEW_REQUIRED)
                reasons.append("Тезис связан с нерешённым временным или иным review-сигналом.")
                focus.append("Проверить хронологию и исходные документы до использования тезиса.")
            elif item.status == TheoryStatus.UNSUPPORTED:
                score += 45
                signals.append(AttackSignalKind.UNSUPPORTED)
                reasons.append("Тезис не имеет валидной доказательственной трассировки.")
                focus.append(
                    "Потребовать первичный источник и проверить допустимость его использования."
                )

            source_count = len(
                {
                    source.get("evidence_id")
                    for source in item.source_refs
                    if source.get("evidence_id")
                }
            )
            fingerprint_count = len(
                {
                    source.get("document_fingerprint")
                    for source in item.source_refs
                    if source.get("document_fingerprint")
                }
            )
            actor_count = len(
                {
                    source.get("actor")
                    for source in item.source_refs
                    if source.get("actor")
                }
            )

            if source_count <= 1:
                score += 20
                signals.append(AttackSignalKind.SINGLE_SOURCE)
                reasons.append("Обвинительный тезис опирается на единственный конкретный источник.")
                focus.append("Проверить, существует ли независимое подтверждение тезиса.")
            if fingerprint_count <= 1:
                score += 10
                signals.append(AttackSignalKind.SINGLE_DOCUMENT_FINGERPRINT)
                reasons.append(
                    "Нет подтверждения из нескольких независимо идентифицированных документов."
                )
            if actor_count <= 1 and any(source.get("actor") for source in item.source_refs):
                score += 10
                signals.append(AttackSignalKind.SINGLE_ACTOR)
                reasons.append(
                    "Доказательственная база зависит от одного участника/источника показаний."
                )
                focus.append("Проверить устойчивость показаний и внешнюю подтверждаемость.")

            defense_sources = tuple(
                source for defense in defense_items for source in defense.source_refs
            )
            if defense_items:
                score += 25
                signals.append(AttackSignalKind.DEFENSE_COUNTERTHESIS)
                reasons.append("По той же теме имеется оформленный защитный контртезис.")
                focus.append(
                    "Сформировать прямой ответ на защитный контртезис и проверить, чем он подтверждён."
                )

            score = min(score, 100)
            ranked.append(
                AttackSurfaceItem(
                    issue_id=item.issue_id,
                    topic=item.topic,
                    statement=item.statement,
                    score=score,
                    severity=self._severity(score),
                    signals=tuple(dict.fromkeys(signals)),
                    reasons=tuple(dict.fromkeys(reasons)),
                    prosecution_sources=item.source_refs,
                    defense_sources=defense_sources,
                    recommended_focus=tuple(dict.fromkeys(focus)),
                )
            )

        ranked.sort(key=lambda entry: (-entry.score, entry.issue_id))
        highest = tuple(entry.issue_id for entry in ranked if entry.score >= 60)
        return AttackSurfaceReport(
            items=tuple(ranked),
            highest_priority_issue_ids=highest,
            requires_human_review=bool(ranked),
        )

    def snapshot(self, report: AttackSurfaceReport) -> dict[str, Any]:
        return {
            "items": [
                {
                    "issue_id": item.issue_id,
                    "topic": item.topic,
                    "statement": item.statement,
                    "score": item.score,
                    "severity": item.severity.value,
                    "signals": [signal.value for signal in item.signals],
                    "reasons": list(item.reasons),
                    "prosecution_sources": list(item.prosecution_sources),
                    "defense_sources": list(item.defense_sources),
                    "recommended_focus": list(item.recommended_focus),
                }
                for item in report.items
            ],
            "highest_priority_issue_ids": list(report.highest_priority_issue_ids),
            "requires_human_review": report.requires_human_review,
        }

    @staticmethod
    def _severity(score: int) -> AttackSeverity:
        if score >= 80:
            return AttackSeverity.CRITICAL
        if score >= 60:
            return AttackSeverity.HIGH
        if score >= 30:
            return AttackSeverity.MEDIUM
        return AttackSeverity.LOW
