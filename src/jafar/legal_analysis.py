import re
from datetime import UTC, date, datetime

from pydantic import ValidationError

from .domains import DocumentTask, MatterType
from .legal_models import Deadline, LegalAnalysis, LegalIssue, RiskLevel
from .model_provider import ModelProvider

DATE_PATTERNS = (
    re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b"),
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
)
CASE_NUMBER = re.compile(r"(?:дело|дела|№)\s*№?\s*([A-Za-zА-Яа-я0-9./-]{4,})", re.IGNORECASE)


class LegalAnalyzer:
    """Provider-neutral first-pass analyzer.

    This layer deliberately does not claim that regex heuristics are legal advice.
    A model provider can replace/enrich this implementation while preserving the
    structured output contract.
    """

    def __init__(self, provider: ModelProvider | None = None) -> None:
        self.provider = provider

    def analyze(self, text: str, task: DocumentTask, matter_type: MatterType) -> LegalAnalysis:
        if self.provider is not None:
            payload = self.provider.analyze(text, task, matter_type)
            if isinstance(payload, dict):
                enriched = {**payload, "task": task, "matter_type": matter_type}
                try:
                    return LegalAnalysis.model_validate(enriched)
                except (TypeError, ValidationError):
                    pass

        normalized = " ".join(text.split())
        issues = self._find_risk_signals(normalized)
        deadlines = self._extract_dates(normalized)
        facts = self._extract_facts(normalized)
        missing = self._missing_information(normalized, matter_type)
        confidence = 0.35 if normalized else 0.0
        if issues or deadlines:
            confidence = 0.55

        return LegalAnalysis(
            task=task,
            matter_type=matter_type,
            summary=self._summary(normalized),
            issues=issues,
            deadlines=deadlines,
            key_facts=facts,
            missing_information=missing,
            confidence=confidence,
            generated_at=datetime.now(UTC),
        )

    def _summary(self, text: str) -> str:
        if len(text) <= 500:
            return text
        return f"{text[:497].rstrip()}..."

    def _find_risk_signals(self, text: str) -> list[LegalIssue]:
        signals: list[tuple[tuple[str, ...], str, str, RiskLevel]] = [
            (("срок", "истекает", "до "), "Процессуальный срок", "В документе обнаружены признаки срока или даты, требующие проверки.", RiskLevel.HIGH),
            (("обжалован", "обжаловать", "апелляц"), "Обжалование", "Обнаружены признаки возможности или необходимости обжалования.", RiskLevel.HIGH),
            (("неустойк", "штраф", "пеня"), "Санкции", "Обнаружены договорные или иные финансовые санкции.", RiskLevel.MEDIUM),
            (("арест", "обыск", "задержан", "уголовн"), "Уголовно-процессуальный риск", "Обнаружены признаки уголовно-процессуального производства или ограничения прав.", RiskLevel.HIGH),
        ]
        result: list[LegalIssue] = []
        lower = text.lower()
        for keywords, title, description, risk in signals:
            if any(keyword in lower for keyword in keywords):
                result.append(LegalIssue(title=title, description=description, risk=risk))
        return result

    def _extract_dates(self, text: str) -> list[Deadline]:
        deadlines: list[Deadline] = []
        for pattern in DATE_PATTERNS:
            for match in pattern.finditer(text):
                try:
                    if len(match.groups()) == 3 and len(match.group(1)) == 4:
                        due = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
                    else:
                        due = date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
                except ValueError:
                    continue
                context = text[max(0, match.start() - 100): min(len(text), match.end() + 100)]
                deadlines.append(Deadline(title="Дата, требующая проверки", due_date=due, source_text=context, confidence=0.65))
        return deadlines

    def _extract_facts(self, text: str) -> list[str]:
        facts: list[str] = []
        match = CASE_NUMBER.search(text)
        if match:
            facts.append(f"Номер дела/производства: {match.group(1)}")
        if "договор" in text.lower():
            facts.append("В документе упоминается договор.")
        if "суд" in text.lower() or "арбитраж" in text.lower():
            facts.append("В документе упоминается суд или арбитраж.")
        return facts

    def _missing_information(self, text: str, matter_type: MatterType) -> list[str]:
        missing: list[str] = []
        if not CASE_NUMBER.search(text):
            missing.append("Номер дела/производства, если он существует.")
        if matter_type in {MatterType.CRIMINAL, MatterType.ARBITRATION, MatterType.CIVIL} and "суд" not in text.lower():
            missing.append("Суд/орган и текущая процессуальная стадия.")
        return missing
