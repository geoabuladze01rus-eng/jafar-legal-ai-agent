from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from .config import settings
from .matter_rag import MatterRAGContext
from .memory_service import LongTermMemoryService


@dataclass(slots=True)
class OpenAIEmbeddingProvider:
    client: OpenAI | None = None
    model: str = "text-embedding-3-small"

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = OpenAI(api_key=settings.openai_api_key)

    def embed(self, text: str) -> tuple[float, ...]:
        if not text.strip():
            raise ValueError("text is required")
        response = self.client.embeddings.create(model=self.model, input=text)
        values = tuple(float(value) for value in response.data[0].embedding)
        if len(values) != 1536:
            raise RuntimeError("unexpected embedding dimension")
        return values


@dataclass(slots=True)
class OpenAIResearchAnswerProvider:
    client: OpenAI | None = None
    model: str = settings.model_name
    memory_service: LongTermMemoryService | None = None
    memory_limit: int = 6

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = OpenAI(api_key=settings.openai_api_key)

    def _memory_context(self, question: str, matter_id: str) -> str:
        if self.memory_service is None:
            return ""
        try:
            memories = self.memory_service.recall(
                question,
                matter_id=matter_id,
                limit=self.memory_limit,
                min_similarity=0.20,
            )
        except (ValueError, RuntimeError):
            return ""
        if not memories:
            return ""
        return "\n".join(
            f"[memory:{item.memory.id}] kind={item.memory.kind.value}; {item.memory.content}"
            for item in memories
        )

    def answer(self, *, question: str, context: MatterRAGContext) -> str:
        if not context.results:
            return "В материалах выбранного дела недостаточно данных для подтвержденного ответа."

        memory_context = self._memory_context(question, context.matter_id)
        user_content = f"QUESTION:\n{question}\n\nMATTER CONTEXT:\n{context.render()}"
        if memory_context:
            user_content += f"\n\nLONG-TERM MEMORY:\n{memory_context}"

        response = self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are Jafar Legal Research. Answer factual and legal questions only from the supplied matter context. "
                        "Do not invent facts, law, citations, dates, or procedural events. "
                        "Every factual proposition about the matter must cite one or more supplied document citation tokens exactly. "
                        "Long-term memory may contain user preferences, prior strategic decisions, workflow rules, or notes. "
                        "Use it only to preserve continuity and preferences; never treat memory as documentary evidence or as proof of a legal fact. "
                        "If memory conflicts with documents, the documents control and you must state the conflict. "
                        "If evidence conflicts or is insufficient, say so explicitly."
                    ),
                },
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
        )
        text = (response.output_text or "").strip()
        if not text:
            raise RuntimeError("research answer provider returned empty text")
        return text
