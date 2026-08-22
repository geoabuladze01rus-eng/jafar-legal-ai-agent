from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from .model_router import ModelProvider, ModelRequest, ModelResponse


@dataclass(frozen=True, slots=True)
class GeminiConfig:
    model: str = "gemini-2.5-pro"
    api_key_env: str = "GEMINI_API_KEY"
    base_url: str = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(ModelProvider):
    """Gemini adapter kept behind the same provider-neutral interface as other models."""

    key = "gemini"

    def __init__(self, config: GeminiConfig | None = None) -> None:
        self.config = config or GeminiConfig()

    def available(self) -> bool:
        return bool(os.getenv(self.config.api_key_env))

    def complete(self, request: ModelRequest) -> ModelResponse:
        api_key = os.getenv(self.config.api_key_env)
        if not api_key:
            raise RuntimeError("Provider gemini is not configured")

        url = f"{self.config.base_url}/{quote(self.config.model)}:generateContent?key={quote(api_key)}"
        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": request.prompt}]}],
        }
        req = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=60) as response:
            data: dict[str, Any] = json.loads(response.read().decode("utf-8"))

        text = self._extract_text(data)
        return ModelResponse(provider=self.key, model=self.config.model, text=text, metadata=data)

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        candidates = data.get("candidates")
        if isinstance(candidates, list) and candidates:
            content = candidates[0].get("content", {})
            if isinstance(content, dict):
                parts = content.get("parts", [])
                if isinstance(parts, list):
                    texts = [p.get("text") for p in parts if isinstance(p, dict) and isinstance(p.get("text"), str)]
                    if texts:
                        return "".join(texts)
        return json.dumps(data, ensure_ascii=False)
