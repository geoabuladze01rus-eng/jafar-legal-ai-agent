from dataclasses import asdict
import json
from typing import Protocol

from jafar.legal_analysis.models import LegalAnalysisResult, LegalRisk, RiskLevel


class LLMClient(Protocol):
    async def analyze(self, system_prompt: str, document_text: str) -> dict: ...


SYSTEM_PROMPT = """Ты — юридический аналитический модуль Джафара. Анализируй только предоставленный документ. Не выдумывай факты, нормы права, судебную практику или сроки. Чётко отделяй установленное текстом от предположений. Верни JSON с полями facts, legal_questions, risks, consequences, recommendations, deadlines, confidence. risks содержит title, explanation, level (low/medium/high/critical), confidence. requires_lawyer_review всегда true."""


class LegalAnalyzer:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def analyze(self, document_id: str, text: str) -> LegalAnalysisResult:
        raw = await self.llm.analyze(SYSTEM_PROMPT, text)
        risks = tuple(
            LegalRisk(
                title=str(item.get("title", "")),
                explanation=str(item.get("explanation", "")),
                level=RiskLevel(str(item.get("level", "medium")).lower()),
                confidence=float(item.get("confidence", 0.0)),
            )
            for item in raw.get("risks", [])
        )
        return LegalAnalysisResult(
            document_id=document_id,
            facts=tuple(map(str, raw.get("facts", []))),
            legal_questions=tuple(map(str, raw.get("legal_questions", []))),
            risks=risks,
            consequences=tuple(map(str, raw.get("consequences", []))),
            recommendations=tuple(map(str, raw.get("recommendations", []))),
            deadlines=tuple(map(str, raw.get("deadlines", []))),
            confidence=float(raw.get("confidence", 0.0)),
            requires_lawyer_review=True,
        )
