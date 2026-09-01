from __future__ import annotations

import json
from dataclasses import dataclass

import httpx
from pydantic import ValidationError

from .config import settings
from .domains import DocumentTask, MatterType
from .legal_models import LegalAnalysis
from .model_router import ModelRequest, ModelResponse


@dataclass(frozen=True)
class OllamaProviderConfig:
    enabled: bool = settings.ollama_enabled
    model: str = settings.ollama_model
    base_url: str = settings.ollama_base_url
    timeout_seconds: float = settings.ollama_timeout_seconds
    health_timeout_seconds: float = settings.ollama_health_timeout_seconds
    keep_alive: str = settings.ollama_keep_alive
    think: bool = settings.ollama_think


class OllamaLegalAnalyzer:
    """Local Ollama provider for private document processing and cheap development runs."""

    key = "ollama"

    def __init__(
        self,
        *,
        config: OllamaProviderConfig | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.config = config or OllamaProviderConfig()
        self.client = client or httpx.Client(
            base_url=self.config.base_url.rstrip("/"),
            timeout=self.config.timeout_seconds,
        )

    def available(self) -> bool:
        if not self.config.enabled:
            return False
        try:
            response = self.client.get("/api/tags", timeout=self.config.health_timeout_seconds)
            response.raise_for_status()
            models = response.json().get("models", [])
        except (httpx.HTTPError, ValueError, TypeError):
            return False

        configured = self.config.model
        return any(
            model.get("name") == configured or model.get("model") == configured
            for model in models
            if isinstance(model, dict)
        )

    def analyze(
        self,
        *,
        text: str,
        task: DocumentTask,
        matter_type: MatterType = MatterType.GENERAL,
    ) -> LegalAnalysis:
        if not text.strip():
            raise ValueError("document text must not be empty")

        schema = LegalAnalysis.model_json_schema()
        schema_text = json.dumps(schema, ensure_ascii=False)
        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Jafar, a local legal document analysis assistant. "
                        "Extract only information supported by the supplied document. "
                        "Do not invent facts, authorities, deadlines, citations, or case law. "
                        "If information is missing or uncertain, state that explicitly. "
                        "Return only data matching the supplied JSON schema."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Task: {task.value}\nMatter type: {matter_type.value}\n\n"
                        f"JSON schema:\n{schema_text}\n\n"
                        "Analyze the following document:\n\n"
                        + text
                    ),
                },
            ],
            "stream": False,
            "format": schema,
            "options": {"temperature": 0},
            "keep_alive": self.config.keep_alive,
            "think": self.config.think,
        }
        data = self._chat(payload)
        content = self._message_content(data)
        try:
            return LegalAnalysis.model_validate_json(content)
        except ValidationError as exc:
            raise RuntimeError("Ollama returned invalid structured legal analysis") from exc

    def complete(self, request: ModelRequest) -> ModelResponse:
        try:
            task = DocumentTask(request.task)
        except ValueError:
            task = None

        if task is not None:
            try:
                matter_type = MatterType(request.matter_type) if request.matter_type else MatterType.GENERAL
            except ValueError:
                matter_type = MatterType.GENERAL
            analysis = self.analyze(text=request.prompt, task=task, matter_type=matter_type)
            return ModelResponse(
                provider=self.key,
                model=self.config.model,
                text=analysis.summary,
                metadata={
                    "legal_analysis": analysis.model_dump(mode="json"),
                    "local": True,
                },
            )

        payload = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "stream": False,
            "keep_alive": self.config.keep_alive,
            "think": self.config.think,
        }
        data = self._chat(payload)
        return ModelResponse(
            provider=self.key,
            model=self.config.model,
            text=self._message_content(data),
            metadata={"local": True},
        )

    def _chat(self, payload: dict) -> dict:
        try:
            response = self.client.post("/api/chat", json=payload, timeout=self.config.timeout_seconds)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise RuntimeError("Ollama request failed") from exc
        if not isinstance(data, dict):
            raise TypeError("Ollama returned an unexpected response")
        return data

    @staticmethod
    def _message_content(data: dict) -> str:
        message = data.get("message")
        if not isinstance(message, dict):
            raise TypeError("Ollama response has no message")
        content = message.get("content")
        if not isinstance(content, str):
            raise TypeError("Ollama response content must be a string")
        if not content.strip():
            raise RuntimeError("Ollama response has no content")
        return content
