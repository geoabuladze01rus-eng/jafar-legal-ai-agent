from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .attack_surface import (
    AttackSignalKind,
    AttackSurfaceItem,
    AttackSurfaceReport,
)


class DefenseActionType(StrEnum):
    VERIFY_SOURCE = "verify_source"
    COMPARE_CONTRADICTION = "compare_contradiction"
    TIMELINE_CHECK = "timeline_check"
    WITNESS_PREP = "witness_prep"
    DOCUMENT_REQUEST = "document_request"
    MOTION_DRAFT = "motion_draft"
    EXPERT_QUESTION = "expert_question"


@dataclass(frozen=True, slots=True)
class DefenseAction:
    action_id: str
    issue_id: str
    topic: str
    action_type: DefenseActionType
    priority: int
    title: str
    rationale: str
    source_refs: tuple[dict[str, Any], ...]
    requires_lawyer_approval: bool = True


@dataclass(frozen=True, slots=True)
class DefenseActionPlan:
    actions: tuple[DefenseAction, ...]
    highest_priority_action_ids: tuple[str, ...]
    requires_lawyer_approval: bool = True


class DefenseActionPlanner:
    """Convert ranked prosecution weak points into source-traceable defense tasks.

    Stable `AttackSignalKind` values drive planning. Human-readable reason text is output
    only and is never parsed as control logic. External legal action still requires lawyer
    approval.
    """

    def build(self, attack_surface: AttackSurfaceReport) -> DefenseActionPlan:
        actions: list[DefenseAction] = []
        for item in attack_surface.items:
            actions.extend(self._actions_for_item(item))

        actions.sort(key=lambda action: (-action.priority, action.action_id))
        highest = tuple(action.action_id for action in actions if action.priority >= 70)
        return DefenseActionPlan(
            actions=tuple(actions),
            highest_priority_action_ids=highest,
        )

    def snapshot(self, plan: DefenseActionPlan) -> dict[str, Any]:
        return {
            "actions": [
                {
                    "action_id": item.action_id,
                    "issue_id": item.issue_id,
                    "topic": item.topic,
                    "action_type": item.action_type.value,
                    "priority": item.priority,
                    "title": item.title,
                    "rationale": item.rationale,
                    "source_refs": list(item.source_refs),
                    "requires_lawyer_approval": item.requires_lawyer_approval,
                }
                for item in plan.actions
            ],
            "highest_priority_action_ids": list(plan.highest_priority_action_ids),
            "requires_lawyer_approval": plan.requires_lawyer_approval,
        }

    def _actions_for_item(self, item: AttackSurfaceItem) -> list[DefenseAction]:
        actions: list[DefenseAction] = []
        combined_sources = tuple((*item.prosecution_sources, *item.defense_sources))
        base_priority = min(100, max(10, item.score))
        signals = set(item.signals)

        actions.append(
            self._action(
                item,
                DefenseActionType.VERIFY_SOURCE,
                base_priority,
                "Перепроверить первичные источники обвинительного тезиса",
                "Сверить документ, страницу, фрагмент, автора и контекст каждого источника до использования в позиции защиты.",
                item.prosecution_sources,
            )
        )

        if item.defense_sources or AttackSignalKind.CONTRADICTED in signals:
            actions.append(
                self._action(
                    item,
                    DefenseActionType.COMPARE_CONTRADICTION,
                    min(100, base_priority + 10),
                    "Сопоставить противоречащие версии",
                    "Подготовить таблицу расхождений с точными ссылками на оба источника и вопросами для предъявления противоречий.",
                    combined_sources,
                )
            )
            actions.append(
                self._action(
                    item,
                    DefenseActionType.WITNESS_PREP,
                    min(100, base_priority + 5),
                    "Подготовить вопросы участнику по противоречиям",
                    "Сформировать нейтральные проверочные вопросы по времени, источнику осведомлённости и изменению показаний; решение о допросе принимает адвокат.",
                    combined_sources,
                )
            )

        if AttackSignalKind.REVIEW_REQUIRED in signals:
            actions.append(
                self._action(
                    item,
                    DefenseActionType.TIMELINE_CHECK,
                    min(100, base_priority + 10),
                    "Проверить хронологию события",
                    "Построить последовательность событий и проверить её по независимым документам, метаданным и иным допустимым источникам.",
                    combined_sources,
                )
            )

        if signals.intersection(
            {
                AttackSignalKind.SINGLE_SOURCE,
                AttackSignalKind.SINGLE_DOCUMENT_FINGERPRINT,
                AttackSignalKind.UNSUPPORTED,
            }
        ):
            actions.append(
                self._action(
                    item,
                    DefenseActionType.DOCUMENT_REQUEST,
                    min(100, base_priority + 5),
                    "Определить недостающие подтверждающие документы",
                    "Составить перечень первичных материалов, которыми обвинение должно подтверждать тезис, и проверить их наличие в деле.",
                    item.prosecution_sources,
                )
            )

        if item.score >= 60:
            actions.append(
                self._action(
                    item,
                    DefenseActionType.MOTION_DRAFT,
                    min(100, base_priority),
                    "Подготовить проект процессуального ходатайства для проверки адвокатом",
                    "Сформировать только черновик возможного ходатайства, привязанный к выявленному пробелу или противоречию; вид, правовое основание и подача требуют отдельного решения адвоката.",
                    combined_sources,
                )
            )

        if any(
            "эксперт" in str(source.get("actor", "")).casefold()
            for source in combined_sources
        ):
            actions.append(
                self._action(
                    item,
                    DefenseActionType.EXPERT_QUESTION,
                    min(100, base_priority + 5),
                    "Подготовить вопросы эксперту",
                    "Сформировать вопросы о методике, исходных данных, границах вывода и альтернативных объяснениях без предрешения оценки заключения.",
                    combined_sources,
                )
            )

        unique: dict[tuple[str, str], DefenseAction] = {}
        for action in actions:
            unique[(action.issue_id, action.action_type.value)] = action
        return list(unique.values())

    @staticmethod
    def _action(
        item: AttackSurfaceItem,
        action_type: DefenseActionType,
        priority: int,
        title: str,
        rationale: str,
        sources: tuple[dict[str, Any], ...],
    ) -> DefenseAction:
        return DefenseAction(
            action_id=f"action:{item.issue_id}:{action_type.value}",
            issue_id=item.issue_id,
            topic=item.topic,
            action_type=action_type,
            priority=priority,
            title=title,
            rationale=rationale,
            source_refs=sources,
        )
