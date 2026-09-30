from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from pydantic import BaseModel, Field

from .encrypted_desktop_corpus import EncryptedDesktopCorpusStore
from .legal_research_service import LegalResearchService
from .matter_rag import MatterRAGContext
from .ollama_provider import OllamaLegalAnalyzer


class DesktopResearchPayload(BaseModel):
    answer: str = Field(min_length=1)
    citations: list[str] = Field(default_factory=list)


class NoopEmbeddingProvider:
    """Desktop lexical retrieval does not need cloud embeddings."""

    def embed(self, text: str) -> Sequence[float]:
        if not text.strip():
            raise ValueError("research question is required")
        return ()


@dataclass(slots=True)
class DesktopMatterRAGProvider:
    store: EncryptedDesktopCorpusStore

    def retrieve(
        self,
        *,
        matter_id: str,
        query: str,
        query_embedding: Sequence[float],
        limit: int = 8,
        min_similarity: float = 0.0,
    ) -> MatterRAGContext:
        del query_embedding
        context = self.store.retrieve(matter_id, query, limit=limit)
        threshold = max(min_similarity, 1e-9)
        return MatterRAGContext(
            matter_id=context.matter_id,
            query=context.query,
            results=tuple(item for item in context.results if item.score >= threshold),
        )


@dataclass(slots=True)
class OllamaDesktopResearchAnswerProvider:
    provider: OllamaLegalAnalyzer

    def answer(self, *, question: str, context: MatterRAGContext) -> str:
        if not context.results:
            return (
                "В материалах выбранного дела не найдено достаточно фрагментов, "
                "чтобы обоснованно ответить на вопрос."
            )

        allowed = set(context.citations)
        payload = self.provider.complete_structured(
            system_prompt=(
                "Ты — локальный юридический ИИ-помощник «Юстиция». "
                "Отвечай только на основании предоставленных фрагментов конкретного дела. "
                "Не придумывай факты, нормы, судебную практику или обстоятельства. "
                "Если данных недостаточно, прямо укажи это. "
                "В citations включай только точные идентификаторы document:... из контекста, "
                "которые действительно подтверждают ответ."
            ),
            user_prompt=(
                f"Вопрос юриста:\n{question}\n\n"
                "Материалы выбранного дела:\n"
                f"{context.render()}"
            ),
            response_model=DesktopResearchPayload,
        )

        citations = tuple(dict.fromkeys(payload.citations))
        if not citations:
            raise RuntimeError("local research answer omitted Matter citations")
        unknown = tuple(ref for ref in citations if ref not in allowed)
        if unknown:
            raise RuntimeError(
                "local research answer cited sources outside selected Matter: "
                + ", ".join(unknown)
            )

        return (
            payload.answer.strip()
            + "\n\nИсточники: "
            + ", ".join(citations)
        )


def build_desktop_legal_research_service(
    store: EncryptedDesktopCorpusStore,
    provider: OllamaLegalAnalyzer,
) -> LegalResearchService:
    return LegalResearchService(
        embeddings=NoopEmbeddingProvider(),
        retrieval=DesktopMatterRAGProvider(store),
        answers=OllamaDesktopResearchAnswerProvider(provider),
    )
