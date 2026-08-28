from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .defense_action_planner import DefenseAction, DefenseActionPlan, DefenseActionType


class PreparationMode(StrEnum):
    HEARING = "hearing"
    INTERROGATION = "interrogation"


@dataclass(frozen=True, slots=True)
class PreparationStep:
    step_id: str
    issue_id: str
    topic: str
    sequence: int
    objective: str
    primary_questions: tuple[str, ...]
    fallback_questions: tuple[str, ...]
    documents_to_present: tuple[dict[str, Any], ...]
    contradiction_sequence: tuple[str, ...]
    caution: str
    requires_lawyer_approval: bool = True


@dataclass(frozen=True, slots=True)
class HearingPreparationPlan:
    mode: PreparationMode
    steps: tuple[PreparationStep, ...]
    document_index: tuple[dict[str, Any], ...]
    requires_lawyer_approval: bool = True


class HearingPreparationEngine:
    """Turn approved-preparation tasks into a source-traceable hearing/interrogation script.

    This engine prepares questions and document order only. It does not contact a witness,
    file a motion, submit evidence, or execute any external legal action.
    """

    def build(
        self,
        action_plan: DefenseActionPlan,
        *,
        mode: PreparationMode = PreparationMode.HEARING,
    ) -> HearingPreparationPlan:
        grouped: dict[str, list[DefenseAction]] = {}
        for action in action_plan.actions:
            grouped.setdefault(action.issue_id, []).append(action)

        ordered_groups = sorted(
            grouped.values(),
            key=lambda actions: (-max(item.priority for item in actions), actions[0].issue_id),
        )

        steps: list[PreparationStep] = []
        all_documents: list[dict[str, Any]] = []
        for sequence, actions in enumerate(ordered_groups, start=1):
            actions = sorted(actions, key=lambda item: (-item.priority, item.action_type.value))
            lead = actions[0]
            sources = self._dedupe_sources(
                source for action in actions for source in action.source_refs
            )
            all_documents.extend(sources)
            steps.append(
                PreparationStep(
                    step_id=f"prep:{lead.issue_id}:{sequence}",
                    issue_id=lead.issue_id,
                    topic=lead.topic,
                    sequence=sequence,
                    objective=self._objective(actions, mode),
                    primary_questions=self._primary_questions(actions, mode),
                    fallback_questions=self._fallback_questions(actions, mode),
                    documents_to_present=tuple(sources),
                    contradiction_sequence=self._contradiction_sequence(actions, sources),
                    caution=(
                        "Проверить процессуальную допустимость вопроса и момента предъявления документа; "
                        "финальную тактику определяет адвокат."
                    ),
                )
            )

        return HearingPreparationPlan(
            mode=mode,
            steps=tuple(steps),
            document_index=tuple(self._dedupe_sources(all_documents)),
        )

    def snapshot(self, plan: HearingPreparationPlan) -> dict[str, Any]:
        return {
            "mode": plan.mode.value,
            "steps": [
                {
                    "step_id": step.step_id,
                    "issue_id": step.issue_id,
                    "topic": step.topic,
                    "sequence": step.sequence,
                    "objective": step.objective,
                    "primary_questions": list(step.primary_questions),
                    "fallback_questions": list(step.fallback_questions),
                    "documents_to_present": list(step.documents_to_present),
                    "contradiction_sequence": list(step.contradiction_sequence),
                    "caution": step.caution,
                    "requires_lawyer_approval": step.requires_lawyer_approval,
                }
                for step in plan.steps
            ],
            "document_index": list(plan.document_index),
            "requires_lawyer_approval": plan.requires_lawyer_approval,
        }

    @staticmethod
    def _objective(actions: list[DefenseAction], mode: PreparationMode) -> str:
        types = {item.action_type for item in actions}
        if DefenseActionType.COMPARE_CONTRADICTION in types:
            return "Зафиксировать источник первоначальной версии, затем последовательно проверить расхождения и причины их появления."
        if DefenseActionType.TIMELINE_CHECK in types:
            return "Уточнить последовательность событий и проверить, совместима ли версия с подтверждённой хронологией."
        if DefenseActionType.EXPERT_QUESTION in types:
            return "Проверить исходные данные, методику, пределы экспертного вывода и альтернативные объяснения."
        if mode == PreparationMode.INTERROGATION:
            return "Проверить источник осведомлённости и устойчивость сообщаемых обстоятельств без навязывания ответа."
        return "Проверить доказательственную основу тезиса и зафиксировать пробелы, требующие дополнительного исследования."

    @staticmethod
    def _primary_questions(actions: list[DefenseAction], mode: PreparationMode) -> tuple[str, ...]:
        types = {item.action_type for item in actions}
        questions: list[str] = [
            "Из какого конкретно источника вам известно это обстоятельство?",
            "Когда и при каких условиях вы впервые сообщили об этом обстоятельстве?",
        ]
        if DefenseActionType.COMPARE_CONTRADICTION in types:
            questions.extend(
                [
                    "Чем объясняется отличие этой версии от ранее зафиксированной?",
                    "Какие обстоятельства позволяют сейчас утверждать именно эту версию?",
                ]
            )
        if DefenseActionType.TIMELINE_CHECK in types:
            questions.extend(
                [
                    "Укажите максимально точно дату и время события.",
                    "Какие документы или объективные данные подтверждают указанное вами время?",
                ]
            )
        if DefenseActionType.EXPERT_QUESTION in types:
            questions.extend(
                [
                    "Какие исходные материалы использованы при исследовании?",
                    "Какие ограничения методики влияют на категоричность вывода?",
                ]
            )
        if mode == PreparationMode.HEARING:
            questions.append("Имеются ли иные независимые источники, подтверждающие это обстоятельство?")
        return tuple(dict.fromkeys(questions))

    @staticmethod
    def _fallback_questions(actions: list[DefenseAction], mode: PreparationMode) -> tuple[str, ...]:
        questions = [
            "Правильно ли я понимаю, что без указанного документа вы не можете назвать иной независимый источник?",
            "Можете ли вы назвать лицо или объективный носитель информации, который подтверждает ваши слова?",
            "Что именно вы наблюдали лично, а что узнали со слов других лиц?",
        ]
        if any(item.action_type == DefenseActionType.TIMELINE_CHECK for item in actions):
            questions.append("Допускаете ли вы, что указанное вами время является приблизительным?")
        if mode == PreparationMode.INTERROGATION:
            questions.append("Какие детали вы можете воспроизвести без обращения к документам или подсказкам?")
        return tuple(questions)

    @staticmethod
    def _contradiction_sequence(
        actions: list[DefenseAction],
        sources: list[dict[str, Any]],
    ) -> tuple[str, ...]:
        if not any(item.action_type == DefenseActionType.COMPARE_CONTRADICTION for item in actions):
            return ()
        sequence = [
            "Сначала получить самостоятельное изложение версии без предъявления противоречащего материала.",
            "Уточнить источник осведомлённости, дату, время и детали события.",
        ]
        for source in sources[:4]:
            label = source.get("document_name") or source.get("evidence_id") or "источник"
            page = source.get("page")
            if page is not None:
                label = f"{label}, стр. {page}"
            sequence.append(f"После фиксации ответа сопоставить с: {label}.")
        sequence.append("Предложить объяснить расхождение; не подсказывать желаемую версию ответа.")
        return tuple(sequence)

    @staticmethod
    def _dedupe_sources(items: Any) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for source in items:
            if not isinstance(source, dict):
                continue
            key = str(source.get("evidence_id") or repr(sorted(source.items())))
            if key in seen:
                continue
            seen.add(key)
            result.append(source)
        return result
