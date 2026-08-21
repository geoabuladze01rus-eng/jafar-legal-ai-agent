import re
from datetime import date, datetime, timezone
from typing import Any

from .domains import DocumentTask, MatterType
from .legal_models import Deadline, LegalAnalysis, LegalIssue, RiskLevel
from .model_provider import ModelProvider


DATE_PATTERNS = (
    re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b"),
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
)
CASE_NUMBER = re.compile(r"(?:дело|дела|№)\s*№?\s*([A-Za-zА-Яа-я0-9./-]{4,})", re.IGNORECASE)


class LegalAnalyzer:
    """Provider-neutral analyzer with a safe deterministic fallback.

    A configured model provider may enrich the structured result. If the provider
    is unavailable, returns malformed data, or times out, the local first-pass
    analysis remains the source of truth rather than failing the request.
    """

    def __init__(self, provider: ModelProvider | None = None) -> None:
        self.provider = provider

    def analyze(self, text: str, task: DocumentTask, matter_type: MatterType) -> LegalAnalysis:
        normalized = " ".join(text.split())
        fallback = self._heuristic_analysis(normalized, task, matter_type)

        if self.provider is None:
            return fallback

        try:
            model_payload = self.provider.analyze(normalized, task, matter_type)
            if not model_payload:
                return fallback
            return self._merge_model_result(fallback, model_payload, task, matter_type)
        except Exception:
            return fallback

    def _heuristic_analysis(self, text: str, task: DocumentTask, matter_type: MatterType) -> LegalAnalysis:
        issues = self._find_risk_signals(text)
        deadlines = self._extract_dates(text)
        facts = self._extract_facts(text)
        missing = self._missing_information(text, matter_type)
        confidence = 0.35 if text else 0.0
        if issues or deadlines:
            confidence = 0.55

        return LegalAnalysis(
            task=task,
            matter_type=matter_type,
            summary=self._summary(text),
            issues=issues,
            deadlines=deadlines,
            key_facts=facts,
            missing_information=missing,
            confidence=confidence,
            generated_at=datetime.now(timezone.utc),
        )

    def _merge_model_result(
        self,
        fallback: LegalAnalysis,
        payload: dict[str, Any],
        task: DocumentTask,
        matter_type: MatterType,
    ) -> LegalAnalysis:
        """Validate model JSON while preserving the stable API contract."""
        candidate = {
            "task": task,
            "matter_type": matter_type,
            "summary": payload.get("summary") or fallback.summary,
            "issues": payload.get("issues", fallback.issues),
            "deadlines": payload.get("deadlines", fallback.deadlines),
            "key_facts": payload.get("key_facts", fallback.key_facts),
            "missing_information": payload.get(
                "missing_information", fallback.missing_information
            ),
            "confidence": payload.get("confidence", fallback.confidence),
            "generated_at": datetime.now(timezone.utc),
        }
        try:
            return LegalAnalysis.model_validate(candidate)
        except Exception:
            return fallback

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
