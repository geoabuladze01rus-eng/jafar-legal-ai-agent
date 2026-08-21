from dataclasses import dataclass, field

from jafar.ai.models import AIProvider, AIRequest
from jafar.ai.prompts import LEGAL_SYSTEM_PROMPT
from jafar.ai.rag import Citation, RAGContext


@dataclass(frozen=True)
class LegalReport:
    summary: str
    facts: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    deadlines: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)


def build_report(provider: AIProvider, question: str, context: RAGContext) -> LegalReport:
    prompt = (
        "Prepare a structured preliminary legal report. Return valid JSON with exactly "
        "these keys: summary, facts, risks, deadlines, missing_information, recommendations. "
        "Each non-summary value must be an array of strings. Do not invent information.\n\n"
        f"SOURCE CONTEXT:\n{context.text}\n\nQUESTION:\n{question}"
    )
    response = provider.complete(AIRequest(LEGAL_SYSTEM_PROMPT, prompt))
    # Parsing/validation is intentionally separated from the transport adapter.
    return LegalReport(summary=response.text, citations=context.citations)
