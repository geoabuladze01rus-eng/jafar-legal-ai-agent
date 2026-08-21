from dataclasses import dataclass


@dataclass(frozen=True)
class Embedding:
    vector: list[float]
    model: str


class EmbeddingProvider:
    """Provider-neutral embeddings boundary; no credentials are stored here."""

    model = "unconfigured"

    def embed(self, text: str) -> Embedding:
        raise NotImplementedError


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, model: str = "text-embedding-3-small") -> None:
        if not api_key:
            raise ValueError("OpenAI API key is required")
        self.api_key = api_key
        self.model = model

    def embed(self, text: str) -> Embedding:
        if not text.strip():
            raise ValueError("Cannot embed empty text")
        # Network transport is intentionally isolated from the search/domain layer.
        raise NotImplementedError("Embedding transport adapter is not configured yet")
