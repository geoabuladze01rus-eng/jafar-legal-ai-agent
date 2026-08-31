from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from .config import settings
from .matter_rag import MatterRAGContext


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

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = OpenAI(api_key=settings.openai_api_key)

    def answer(self, *, question: str, context: MatterRAGContext) -> str:
        if not context.results:
            return "В материалах выбранного дела недостаточно данных для подтвержденного ответа."

        response = self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are Jafar Legal Research. Answer only from the supplied matter context. "
                        "Do not invent facts, law, citations, dates, or procedural events. "
                        "Every factual proposition must cite one or more supplied citation tokens exactly. "
                        "If evidence conflicts or is insufficient, say so explicitly."
                    ),
                },
                {
                    "role": "user",
                    "content": f"QUESTION:\n{question}\n\nMATTER CONTEXT:\n{context.render()}",
                },
            ],
        )
        text = (response.output_text or "").strip()
        if not text:
            raise RuntimeError("research answer provider returned empty text")
        return text
