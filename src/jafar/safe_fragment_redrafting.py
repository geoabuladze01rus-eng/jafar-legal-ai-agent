from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .doctrine_case_impact import DoctrineImpactUrgency
from .work_product_dependency_graph import (
    FragmentDependencyImpact,
    WorkProductDependencyReport,
    WorkProductFragment,
)


class RedraftOptionKind(StrEnum):
    PRESERVE_WITH_CAVEAT = "preserve_with_caveat"
    NARROW_ARGUMENT = "narrow_argument"
    REPLACE_AUTHORITY = "replace_authority"
    REMOVE_UNSUPPORTED_POINT = "remove_unsupported_point"
    REFRAME_ARGUMENT = "reframe_argument"
    HUMAN_RESEARCH_REQUIRED = "human_research_required"


@dataclass(frozen=True, slots=True)
class RedraftOption:
    kind: RedraftOptionKind
    instruction: str
    rationale: str
    requires_authority_verification: bool = True


@dataclass(frozen=True, slots=True)
class FragmentRedraftPacket:
    fragment_id: str
    work_product_id: str
    original_text: str
    source_refs: tuple[str, ...]
    authority_ids: tuple[str, ...]
    rule_ids: tuple[str, ...]
    urgency: DoctrineImpactUrgency
    stale: bool
    risk_reasons: tuple[str, ...]
    options: tuple[RedraftOption, ...]
    mandatory_checks: tuple[str, ...]
    may_auto_apply: bool = False
    requires_lawyer_approval: bool = True


@dataclass(frozen=True, slots=True)
class FragmentRedraftReport:
    work_product_id: str
    packets: tuple[FragmentRedraftPacket, ...]
    blocked_fragment_ids: tuple[str, ...]
    requires_lawyer_review: bool


class SafeFragmentRedraftingEngine:
    """Prepare lawyer-review packets for risky fragments without rewriting source text.

    The engine never produces an automatically applied replacement. It preserves the exact
    original fragment and provides bounded editing strategies plus mandatory verification
    checks derived from explicit dependency impacts.
    """

    def prepare(
        self,
        *,
        dependency_report: WorkProductDependencyReport,
        fragments: tuple[WorkProductFragment, ...],
    ) -> FragmentRedraftReport:
        by_id = {fragment.fragment_id: fragment for fragment in fragments}
        packets: list[FragmentRedraftPacket] = []

        for impact in dependency_report.impacts:
            if not self._needs_packet(impact):
                continue
            fragment = by_id.get(impact.fragment_id)
            if fragment is None:
                continue
            packets.append(self._packet(fragment, impact))

        packets.sort(key=lambda packet: (-self._urgency_rank(packet.urgency), packet.fragment_id))
        blocked = tuple(packet.fragment_id for packet in packets)
        return FragmentRedraftReport(
            work_product_id=dependency_report.work_product_id,
            packets=tuple(packets),
            blocked_fragment_ids=blocked,
            requires_lawyer_review=bool(packets),
        )

    @staticmethod
    def release_ready(report: FragmentRedraftReport) -> bool:
        return not report.blocked_fragment_ids

    @staticmethod
    def _needs_packet(impact: FragmentDependencyImpact) -> bool:
        return impact.stale or impact.urgency in {
            DoctrineImpactUrgency.HIGH,
            DoctrineImpactUrgency.CRITICAL,
        }

    def _packet(
        self,
        fragment: WorkProductFragment,
        impact: FragmentDependencyImpact,
    ) -> FragmentRedraftPacket:
        options = self._options(impact)
        checks = self._mandatory_checks(fragment, impact)
        return FragmentRedraftPacket(
            fragment_id=fragment.fragment_id,
            work_product_id=fragment.work_product_id,
            original_text=fragment.text,
            source_refs=fragment.source_refs,
            authority_ids=fragment.authority_ids,
            rule_ids=fragment.rule_ids,
            urgency=impact.urgency,
            stale=impact.stale,
            risk_reasons=impact.reasons,
            options=options,
            mandatory_checks=checks,
        )

    @staticmethod
    def _options(impact: FragmentDependencyImpact) -> tuple[RedraftOption, ...]:
        options: list[RedraftOption] = []
        reasons = " ".join(impact.reasons).casefold()

        if impact.stale:
            options.append(
                RedraftOption(
                    kind=RedraftOptionKind.REPLACE_AUTHORITY,
                    instruction="Проверить актуальный verified authority и заменить устаревшую опору только после подтверждения применимости.",
                    rationale="Фрагмент помечен stale из-за изменения доктрины.",
                )
            )
        if "сужена" in reasons or "исключение" in reasons:
            options.append(
                RedraftOption(
                    kind=RedraftOptionKind.NARROW_ARGUMENT,
                    instruction="Сузить формулировку довода до фактов и условий, которые остаются внутри актуальной области правила.",
                    rationale="Последующая практика ограничивает область применения исходного довода.",
                )
            )
        if "конфликт" in reasons:
            options.append(
                RedraftOption(
                    kind=RedraftOptionKind.HUMAN_RESEARCH_REQUIRED,
                    instruction="Не выбирать победившую позицию автоматически; провести проверку conflict treatment и более поздних authorities.",
                    rationale="Подтверждённый конфликт не может быть разрешён модельным голосованием.",
                )
            )
        if impact.urgency == DoctrineImpactUrgency.HIGH and not impact.stale:
            options.append(
                RedraftOption(
                    kind=RedraftOptionKind.PRESERVE_WITH_CAVEAT,
                    instruction="Сохранить исходный довод только с явной оговоркой о нерешённом doctrinal/freshness сигнале после проверки юристом.",
                    rationale="Фрагмент ещё не признан устаревшим, но требует повышенной проверки.",
                )
            )
        if not options:
            options.append(
                RedraftOption(
                    kind=RedraftOptionKind.REFRAME_ARGUMENT,
                    instruction="Переформулировать довод после проверки актуального правила, не меняя фактическую основу без подтверждённого источника.",
                    rationale="Фрагмент требует юридической переработки, но безопасная стратегия не определяется автоматически.",
                )
            )
        return tuple(options)

    @staticmethod
    def _mandatory_checks(
        fragment: WorkProductFragment,
        impact: FragmentDependencyImpact,
    ) -> tuple[str, ...]:
        checks = [
            "Подтвердить canonical citation и официальный источник каждого authority, на который будет опираться новая редакция.",
            "Повторно проверить applicability по юридически значимой дате, виду производства и теме дела.",
            "Проверить precedent freshness и отсутствие unresolved/conflicting treatment.",
            "Сверить новую редакцию с фактическими source_refs исходного фрагмента.",
            "Получить явное одобрение юриста перед заменой текста в рабочем документе.",
        ]
        if impact.matched_rule_ids or fragment.rule_ids:
            checks.append("Проверить, что используемый normalized rule остаётся current и не superseded.")
        return tuple(checks)

    @staticmethod
    def _urgency_rank(value: DoctrineImpactUrgency) -> int:
        return {
            DoctrineImpactUrgency.LOW: 1,
            DoctrineImpactUrgency.MEDIUM: 2,
            DoctrineImpactUrgency.HIGH: 3,
            DoctrineImpactUrgency.CRITICAL: 4,
        }[value]
