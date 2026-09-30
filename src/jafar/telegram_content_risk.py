from __future__ import annotations

import re
from dataclasses import dataclass

from .telegram_publication import PublicationRisk, RiskLevel


_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+7|8)[\s()\-]*\d{3}[\s()\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}(?!\d)"
)
_CASE_RE = re.compile(r"\b(?:дел[оа]|уд)\s*(?:№|N)?\s*\d{6,}(?:[/\-]\d+)*\b", re.IGNORECASE)
_PASSPORT_RE = re.compile(r"\b\d{2}\s?\d{2}\s?\d{6}\b")
_BANK_CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_ADDRESS_HINT_RE = re.compile(
    r"\b(?:ул\.?|улица|проспект|пр-т|переулок|пер\.?|дом|д\.|квартира|кв\.)"
    r"\s+[^\n,;]{2,60}",
    re.IGNORECASE,
)
_CURRENT_CASE_HINT_RE = re.compile(
    r"\b(?:текущее дело|по нашему делу|мой доверитель|наш доверитель|следователь по делу|"
    r"обвиняемый по делу|подозреваемый по делу|материалы дела|уголовное дело №)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class RiskFinding:
    kind: str
    severity: RiskLevel
    start: int
    end: int
    redacted_preview: str


@dataclass(frozen=True, slots=True)
class ContentRiskAssessment:
    risk: PublicationRisk
    findings: tuple[RiskFinding, ...]

    @property
    def requires_human_review(self) -> bool:
        return (
            self.risk.current_case_risk
            or self.risk.privacy_risk is not RiskLevel.LOW
            or self.risk.legal_risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}
        )


class TelegramContentRiskGuard:
    """Conservative pre-publication detector for sensitive case and personal data.

    The guard never attempts to decide whether detected data may lawfully be published.
    Any detected personal-data signal is routed to human review instead.
    """

    def assess(self, text: str, *, current_case: bool = False) -> ContentRiskAssessment:
        findings: list[RiskFinding] = []
        self._collect(findings, text, "email", RiskLevel.MEDIUM, _EMAIL_RE)
        self._collect(findings, text, "phone", RiskLevel.MEDIUM, _PHONE_RE)
        self._collect(findings, text, "case_number", RiskLevel.HIGH, _CASE_RE)
        self._collect(findings, text, "passport", RiskLevel.CRITICAL, _PASSPORT_RE)
        self._collect(findings, text, "bank_card", RiskLevel.CRITICAL, _BANK_CARD_RE)
        self._collect(findings, text, "address", RiskLevel.HIGH, _ADDRESS_HINT_RE)

        inferred_current_case = current_case or bool(_CURRENT_CASE_HINT_RE.search(text))
        privacy_risk = max(
            (item.severity for item in findings),
            default=RiskLevel.LOW,
            key=_risk_rank,
        )
        flags = [item.kind for item in findings]
        if inferred_current_case:
            flags.append("current_case_context")

        risk = PublicationRisk(
            legal_risk=RiskLevel.HIGH if inferred_current_case else RiskLevel.LOW,
            privacy_risk=privacy_risk,
            current_case_risk=inferred_current_case,
            flags=sorted(set(flags)),
        )
        return ContentRiskAssessment(risk=risk, findings=tuple(findings))

    def redact(self, text: str) -> str:
        redacted = text
        replacements = (
            (_EMAIL_RE, "[EMAIL REDACTED]"),
            (_PHONE_RE, "[PHONE REDACTED]"),
            (_PASSPORT_RE, "[PASSPORT REDACTED]"),
            (_BANK_CARD_RE, "[PAYMENT DATA REDACTED]"),
            (_CASE_RE, "[CASE NUMBER REDACTED]"),
            (_ADDRESS_HINT_RE, "[ADDRESS REDACTED]"),
        )
        for pattern, marker in replacements:
            redacted = pattern.sub(marker, redacted)
        return redacted

    @staticmethod
    def _collect(
        findings: list[RiskFinding],
        text: str,
        kind: str,
        severity: RiskLevel,
        pattern: re.Pattern[str],
    ) -> None:
        for match in pattern.finditer(text):
            findings.append(
                RiskFinding(
                    kind=kind,
                    severity=severity,
                    start=match.start(),
                    end=match.end(),
                    redacted_preview=f"[{kind.upper()} REDACTED]",
                )
            )


def _risk_rank(level: RiskLevel) -> int:
    return {
        RiskLevel.LOW: 0,
        RiskLevel.MEDIUM: 1,
        RiskLevel.HIGH: 2,
        RiskLevel.CRITICAL: 3,
    }[level]
