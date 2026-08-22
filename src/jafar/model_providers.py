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
    """Small stdlib provider adapter; keeps credentials outside source code."""

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
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=60) as response:
            data: dict[str, Any] = json.loads(response.read().decode("utf-8"))

        text = self._extract_text(data)
        return ModelResponse(provider=self.key, model=self.config.model, text=text, metadata=data)

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


def default_providers() -> dict[str, ModelProvider]:
    return {
        "openai": HTTPModelProvider(HTTPProviderConfig("openai", os.getenv("OPENAI_MODEL", "gpt-5.6"), "OPENAI_API_KEY", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"))),
        "deepseek": HTTPModelProvider(HTTPProviderConfig("deepseek", os.getenv("DEEPSEEK_MODEL", "deepseek-chat"), "DEEPSEEK_API_KEY", os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/chat/completions"))),
        "gemini": GeminiProvider(),
    }
