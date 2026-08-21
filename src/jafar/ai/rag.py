from dataclasses import dataclass

from jafar.ai.models import AIProvider, AIRequest
from jafar.search.in_memory import InMemorySearch


@dataclass(frozen=True)
class Citation:
    chunk_id: str
    source: str


@dataclass(frozen=True)
class RAGContext:
    text: str
    citations: list[Citation]


def build_context(search: InMemorySearch, query: str, limit: int = 8) -> RAGContext:
    results = search.search(query, limit=limit)
    text = "\n\n".join(
        f"[SOURCE {item.chunk_id}]\n{item.text}" for item in results
    )
    citations = [Citation(item.chunk_id, item.source) for item in results]
    return RAGContext(text=text, citations=citations)


def answer_with_context(
    provider: AIProvider,
    system_prompt: str,
    query: str,
    context: RAGContext,
) -> tuple[str, list[Citation]]:
    prompt = (
        "Use only the supplied source context for factual claims. "
        "If the context is insufficient, say so explicitly. "
        "Preserve source identifiers when referring to evidence.\n\n"
        f"SOURCE CONTEXT:\n{context.text}\n\nQUESTION:\n{query}"
    )
    response = provider.complete(AIRequest(system_prompt=system_prompt, user_prompt=prompt))
    return response.text, context.citations
