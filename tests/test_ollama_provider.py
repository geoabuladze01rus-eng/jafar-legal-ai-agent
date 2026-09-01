from __future__ import annotations

import json

import httpx

from jafar.domains import DocumentTask, MatterType
from jafar.model_router import ModelRequest
from jafar.ollama_provider import OllamaLegalAnalyzer, OllamaProviderConfig


def make_client(handler) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://ollama.test",
    )


def test_available_requires_configured_model_to_be_installed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={"models": [{"name": "qwen3:4b", "model": "qwen3:4b"}]},
        )

    provider = OllamaLegalAnalyzer(
        config=OllamaProviderConfig(model="qwen3:4b", base_url="http://ollama.test"),
        client=make_client(handler),
    )
    assert provider.available() is True


def test_available_is_false_when_daemon_is_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    provider = OllamaLegalAnalyzer(
        config=OllamaProviderConfig(model="qwen3:4b", base_url="http://ollama.test"),
        client=make_client(handler),
    )
    assert provider.available() is False


def test_structured_legal_analysis_uses_json_schema_and_preserves_matter_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3:4b"}]})

        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["model"] == "qwen3:4b"
        assert body["stream"] is False
        assert body["options"]["temperature"] == 0
        assert body["format"]["type"] == "object"
        assert "Matter type: criminal" in body["messages"][1]["content"]

        legal_analysis = {
            "task": "legal_analysis",
            "matter_type": "criminal",
            "summary": "В документе указано изъятие автомобиля.",
            "issues": [],
            "deadlines": [],
            "key_facts": ["Автомобиль изъят."],
            "missing_information": [],
            "confidence": 0.9,
        }
        return httpx.Response(
            200,
            json={
                "model": "qwen3:4b",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(legal_analysis, ensure_ascii=False),
                },
                "done": True,
            },
        )

    provider = OllamaLegalAnalyzer(
        config=OllamaProviderConfig(model="qwen3:4b", base_url="http://ollama.test"),
        client=make_client(handler),
    )
    response = provider.complete(
        ModelRequest(
            prompt="Автомобиль был изъят.",
            task=DocumentTask.LEGAL_ANALYSIS.value,
            matter_type=MatterType.CRIMINAL.value,
        )
    )

    assert response.provider == "ollama"
    assert response.model == "qwen3:4b"
    assert response.metadata["local"] is True
    assert response.metadata["legal_analysis"]["matter_type"] == "criminal"
    assert response.text == "В документе указано изъятие автомобиля."
