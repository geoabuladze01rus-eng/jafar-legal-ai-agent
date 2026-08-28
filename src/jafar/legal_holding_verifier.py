from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re

from .legal_proposition_extractor import PropositionCandidate


class HoldingStatus(StrEnum):
    VERIFIED_HOLDING = "verified_holding"
    PARTY_ARGUMENT = "party_argument"
    LOWER_COURT_POSITION = "lower_court_position"
    FACTUAL_NARRATIVE = "factual_narrative"
    QUOTED_AUTHORITY = "quoted_authority"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True, slots=True)
class HoldingVerificationResult:
    proposition: PropositionCandidate
    status: HoldingStatus
    confidence: float
    reasons: tuple[str, ...]
    may_enter_holding_base: bool


class LegalHoldingVerifier:
    """Classify proposition candidates without promoting ambiguous text to court holdings."""

    PARTY_MARKERS = (
        "заявитель указал",
        "осужденный указал",
        "осуждённый указал",
        "адвокат указал",
        "защитник указал",
        "прокурор указал",
        "в жалобе указано",
        "по мнению защиты",
        "по мнению стороны",
        "сторона ссылается",
        "доводы жалобы",
    )
    LOWER_COURT_MARKERS = (
        "суд первой инстанции указал",
        "апелляционный суд указал",
        "нижестоящий суд указал",
        "судом первой инстанции установлено",
        "апелляционным определением установлено",
    )
    FACT_MARKERS = (
        "судом установлено, что",
        "из материалов дела следует",
        "как следует из материалов дела",
        "установлено, что",
        "согласно материалам дела",
    )
    OWN_HOLDING_MARKERS = (
        "верховный суд указал",
        "судебная коллегия указала",
        "судебная коллегия пришла к выводу",
        "суд пришел к выводу",
        "суд пришёл к выводу",
        "следует исходить из того, что",
        "необходимо учитывать, что",
        "не допускается",
        "не может быть признано",
        "подлежит применению",
    )
    QUOTE_MARKERS = (
        "как разъяснено в",
        "согласно позиции",
        "в постановлении пленума указано",
        "конституционный суд указал",
    )

    def verify(self, proposition: PropositionCandidate) -> HoldingVerificationResult:
        text = " ".join(proposition.text.split())
        lowered = text.casefold()
        reasons: list[str] = []

        if any(marker in lowered for marker in self.PARTY_MARKERS):
            reasons.append("Фрагмент содержит маркер позиции стороны, а не собственного вывода суда.")
            return self._result(proposition, HoldingStatus.PARTY_ARGUMENT, 0.95, reasons, False)

        if any(marker in lowered for marker in self.LOWER_COURT_MARKERS):
            reasons.append("Фрагмент описывает позицию нижестоящего суда.")
            return self._result(proposition, HoldingStatus.LOWER_COURT_POSITION, 0.93, reasons, False)

        if any(marker in lowered for marker in self.QUOTE_MARKERS):
            reasons.append("Фрагмент содержит цитирование или пересказ внешнего authority.")
            return self._result(proposition, HoldingStatus.QUOTED_AUTHORITY, 0.9, reasons, False)

        if any(marker in lowered for marker in self.FACT_MARKERS):
            if not any(marker in lowered for marker in self.OWN_HOLDING_MARKERS):
                reasons.append("Фрагмент относится к описанию фактов/материалов дела, а не к правовому выводу.")
                return self._result(proposition, HoldingStatus.FACTUAL_NARRATIVE, 0.88, reasons, False)

        own_marker = next((marker for marker in self.OWN_HOLDING_MARKERS if marker in lowered), None)
        if own_marker is None:
            reasons.append("Недостаточно признаков собственного правового вывода суда.")
            return self._result(proposition, HoldingStatus.REVIEW_REQUIRED, 0.4, reasons, False)

        if self._looks_like_reported_speech(lowered, own_marker):
            reasons.append("Маркер судебного вывода находится внутри пересказа чужой позиции; требуется ручная проверка контекста.")
            return self._result(proposition, HoldingStatus.REVIEW_REQUIRED, 0.55, reasons, False)

        reasons.append(f"Обнаружен маркер собственного вывода суда: {own_marker}.")
        reasons.append("Фрагмент не содержит явных маркеров позиции стороны, нижестоящего суда или фактического пересказа.")
        return self._result(proposition, HoldingStatus.VERIFIED_HOLDING, 0.82, reasons, True)

    def verify_many(
        self,
        propositions: tuple[PropositionCandidate, ...],
    ) -> tuple[HoldingVerificationResult, ...]:
        return tuple(self.verify(item) for item in propositions)

    @staticmethod
    def accepted_holdings(
        results: tuple[HoldingVerificationResult, ...],
    ) -> tuple[HoldingVerificationResult, ...]:
        return tuple(
            item
            for item in results
            if item.status == HoldingStatus.VERIFIED_HOLDING and item.may_enter_holding_base
        )

    @staticmethod
    def _looks_like_reported_speech(text: str, own_marker: str) -> bool:
        index = text.find(own_marker)
        if index <= 0:
            return False
        prefix = text[max(0, index - 140):index]
        return bool(
            re.search(
                r"(?:утверждает|указывает|полагает|считает|ссылается|довод[аы]?)[^.!?]{0,120}$",
                prefix,
            )
        )

    @staticmethod
    def _result(
        proposition: PropositionCandidate,
        status: HoldingStatus,
        confidence: float,
        reasons: list[str],
        may_enter: bool,
    ) -> HoldingVerificationResult:
        return HoldingVerificationResult(
            proposition=proposition,
            status=status,
            confidence=confidence,
            reasons=tuple(reasons),
            may_enter_holding_base=may_enter,
        )
