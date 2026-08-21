from dataclasses import dataclass

from jafar.ai.models import AIProvider
from jafar.ai.report import LegalReport, build_report
from jafar.ai.rag import RAGContext, build_context
from jafar.search.in_memory import InMemorySearch


@dataclass(frozen=True)
class DocumentAnalysis:
    question: str
    report: LegalReport
    context: RAGContext


def analyze_with_retrieval(
    provider: AIProvider,
    search: InMemorySearch,
    question: str,
    limit: int = 8,
) -> DocumentAnalysis:
    context = build_context(search, question, limit=limit)
    if not context.citations:
        raise ValueError("Cannot perform grounded legal analysis without source evidence")
    report = build_report(provider, question, context)
    return DocumentAnalysis(question=question, report=report, context=context)
