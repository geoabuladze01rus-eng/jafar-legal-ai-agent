from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from .gemini_provider import GeminiProvider
from .model_router import ModelProvider, ModelRequest, ModelResponse


@dataclass(frozen=True, slots=True)
class HTTPProviderConfig:
    key: str
    model: str
    api_key_env: str
    endpoint: str


class HTTPModelProvider(ModelProvider):
    """OpenAI-compatible adapter for providers exposing chat-completions semantics."""

    def __init__(self, config: HTTPProviderConfig) -> None:
        self.config = config
        self.key = config.key

    def available(self) -> bool:
        return bool(os.getenv(self.config.api_key_env))

    def complete(self, request: ModelRequest) -> ModelResponse:
        api_key = os.getenv(self.config.api_key_env)
        if not api_key:
            raise RuntimeError(f"Provider {self.key} is not configured")
        payload = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        body = json.dumps(payload).encode("utf-8")
        req = Request(
            self.config.endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(req, timeout=60) as response:
            data: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        return ModelResponse(
            provider=self.key,
            model=self.config.model,
            text=self._extract_text(data),
            metadata=data,
        )

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {})
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
        if isinstance(data.get("text"), str):
            return data["text"]
        return json.dumps(data, ensure_ascii=False)


class OpenAIResponsesProvider(ModelProvider):
    """Native OpenAI Responses API adapter."""

    key = "openai"

    def __init__(self) -> None:
        self.model = os.getenv("OPENAI_MODEL", "gpt-5.6")
        self.endpoint = os.getenv("OPENAI_RESPONSES_URL", "https://api.openai.com/v1/responses")

    def available(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def complete(self, request: ModelRequest) -> ModelResponse:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("Provider openai is not configured")
        payload = {"model": self.model, "input": request.prompt}
        req = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(req, timeout=60) as response:
            data: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        text = data.get("output_text")
        if not isinstance(text, str):
            text = json.dumps(data, ensure_ascii=False)
        return ModelResponse(provider=self.key, model=self.model, text=text, metadata=data)


def _alibaba_chat_url() -> str:
    """Return the deployment-specific Model Studio chat-completions endpoint.

    New Model Studio workspaces use region/workspace-specific endpoints. The US DashScope
    compatibility endpoint remains a practical fallback for deployments that support it,
    while production should set ALIBABA_MODEL_STUDIO_CHAT_URL explicitly.
    """

    return os.getenv(
        "ALIBABA_MODEL_STUDIO_CHAT_URL",
        "https://dashscope-us.aliyuncs.com/compatible-mode/v1/chat/completions",
    )


def default_providers() -> dict[str, ModelProvider]:
    alibaba_endpoint = _alibaba_chat_url()
    return {
        "openai": OpenAIResponsesProvider(),
        "deepseek": HTTPModelProvider(
            HTTPProviderConfig(
                "deepseek",
                os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                "DEEPSEEK_API_KEY",
                os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/chat/completions"),
            )
        ),
        "qwen": HTTPModelProvider(
            HTTPProviderConfig(
                "qwen",
                os.getenv("QWEN_MODEL", "qwen3.8-max"),
                "DASHSCOPE_API_KEY",
                alibaba_endpoint,
            )
        ),
        "kimi": HTTPModelProvider(
            HTTPProviderConfig(
                "kimi",
                os.getenv("KIMI_MODEL", "kimi-k3"),
                "DASHSCOPE_API_KEY",
                alibaba_endpoint,
            )
        ),
        "gemini": GeminiProvider(),
    }
