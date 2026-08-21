from jafar.ai.models import AIProvider, AIRequest, AIResponse


class OpenAIProvider(AIProvider):
    """Lazy OpenAI adapter; keeps the SDK/network dependency outside domain code."""

    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-5.6") -> None:
        if not api_key:
            raise ValueError("OpenAI API key is required")
        self.api_key = api_key
        self.model = model

    def complete(self, request: AIRequest) -> AIResponse:
        # The concrete SDK call is intentionally isolated here so model/provider
        # changes do not affect the legal domain or RAG layers.
        raise NotImplementedError("OpenAI transport adapter is not configured yet")
