from jafar.model_router import ModelRequest, ModelResponse, ModelRouter


class FakeProvider:
    def __init__(self, key: str, *, available: bool = True) -> None:
        self.key = key
        self._available = available

    def available(self) -> bool:
        return self._available

    def complete(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(self.key, "test-model", request.prompt, {})


def _providers() -> dict[str, FakeProvider]:
    return {
        "openai": FakeProvider("openai"),
        "gemini": FakeProvider("gemini"),
        "deepseek": FakeProvider("deepseek"),
        "qwen": FakeProvider("qwen"),
        "kimi": FakeProvider("kimi"),
    }


def test_second_opinion_prefers_qwen_when_non_confidential() -> None:
    decision = ModelRouter(_providers()).decide(
        ModelRequest("analyze", "second_opinion", confidential=False)
    )
    assert decision.primary == "qwen"


def test_long_context_prefers_kimi_when_non_confidential() -> None:
    decision = ModelRouter(_providers()).decide(
        ModelRequest("analyze", "cross_document_analysis", confidential=False)
    )
    assert decision.primary == "kimi"


def test_vision_keeps_gemini_role() -> None:
    decision = ModelRouter(_providers()).decide(
        ModelRequest("analyze", "legal_analysis", requires_vision=True, confidential=False)
    )
    assert decision.primary == "gemini"


def test_confidential_request_does_not_leak_to_qwen_or_kimi_by_default() -> None:
    decision = ModelRouter(_providers()).decide(
        ModelRequest("secret", "second_opinion", confidential=True)
    )
    assert decision.primary == "openai"
