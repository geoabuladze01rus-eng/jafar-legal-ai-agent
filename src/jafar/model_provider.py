from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from .domains import DocumentTask, MatterType


class ModelProvider(Protocol):
    """Provider-neutral contract for structured legal analysis."""

    def analyze(self, text: str, task: DocumentTask, matter_type: MatterType) -> dict[str, Any] | None:
        ...


@dataclass(frozen=True)
class OpenAICompatibleProvider:
    """Small stdlib-only client for OpenAI-compatible chat-completions APIs.

    The client is intentionally optional: when no API key is configured, callers
    can keep using the deterministic local analyzer without making network calls.
    """

    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = 30.0

    def analyze(self, text: str, task: DocumentTask, matter_type: MatterType) -> dict[str, Any] | None:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        prompt = self._prompt(text, task, matter_type)
        payload = {
            "model": self.model,
            "temperature": 0.1,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты — модуль предварительного анализа юридических документов. "
                        "Не выдумывай факты, нормы права или сроки. Возвращай только JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"]
            return self._parse_json(content)
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def _prompt(text: str, task: DocumentTask, matter_type: MatterType) -> str:
        schema = {
            "summary": "string",
            "issues": [
                {
                    "title": "string",
                    "description": "string",
                    "risk": "low|medium|high|critical|unknown",
                    "source_text": "string|null",
                }
            ],
            "deadlines": [
                {
                    "title": "string",
                    "due_date": "YYYY-MM-DD|null",
                    "source_text": "string|null",
                    "confidence": "number 0..1",
                }
            ],
            "key_facts": ["string"],
            "missing_information": ["string"],
            "confidence": "number 0..1",
        }
        return (
            f"Задача: {task.value}\n"
            f"Тип дела: {matter_type.value}\n"
            f"Верни JSON по схеме: {json.dumps(schema, ensure_ascii=False)}\n\n"
            f"Текст документа:\n{text}"
        )

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any] | None:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.removeprefix("json")
        value = json.loads(cleaned)
        if not isinstance(value, dict):
            return None
        return value


@dataclass(frozen=True)
class GeminiProvider:
    """Configuration-only Gemini boundary; transport is injected for tests."""

    api_key: str = ""
    model: str = ""
    enabled: bool = False
    transport: Any = None

    def analyze(self, text: str, task: DocumentTask, matter_type: MatterType) -> dict[str, Any] | None:
        if not self.enabled or self.transport is None:
            return None
        request = {"model": self.model, "contents": [{"role": "user", "parts": [{"text": self._prompt(text, task, matter_type)}]}]}
        response = self.transport(request)
        if not isinstance(response, dict):
            return None
        candidate = response.get("text") or response.get("content")
        return self._parse_json(candidate) if isinstance(candidate, str) else None

    @staticmethod
    def _prompt(text: str, task: DocumentTask, matter_type: MatterType) -> str:
        return f"Task: {task.value}; matter_type: {matter_type.value}\n{text}"

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any] | None:
        try:
            value = json.loads(content)
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None


@dataclass(frozen=True)
class DeepSeekProvider:
    """Disabled-by-default provider contract with injected transport."""
    api_key: str = ""
    model: str = ""
    enabled: bool = False
    transport: Any = None

    def analyze(self, text: str, task: DocumentTask, matter_type: MatterType) -> dict[str, Any] | None:
        if not self.enabled or self.transport is None:
            return None
        response = self.transport({"model": self.model, "prompt": text, "task": task.value})
        return response if isinstance(response, dict) else None
