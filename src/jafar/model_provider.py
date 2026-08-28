from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from .domains import DocumentTask, MatterType
from .openai_diagnostics import classify_http_error, classify_openai_failure


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
    transport: Any = None

    def analyze(self, text: str, task: DocumentTask, matter_type: MatterType) -> dict[str, Any] | None:
        result, _category, _status = self.analyze_with_diagnostics(text, task, matter_type)
        return result

    def analyze_with_diagnostics(self, text: str, task: DocumentTask, matter_type: MatterType) -> tuple[dict[str, Any] | None, str | None, int | None]:
        url = f"{self.base_url.rstrip('/')}/responses"
        prompt = self._prompt(text, task, matter_type)
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": (
                        "Ты — модуль предварительного анализа юридических документов. "
                        "Не выдумывай факты, нормы права или сроки. Возвращай только JSON."
                    )}],
                },
                {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
            ],
            "temperature": 0.1,
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
            opener = self.transport or urllib.request.urlopen
            with opener(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
            content = self._extract_content(body)
            parsed = self._parse_json(content)
            return parsed, None, None
        except urllib.error.HTTPError as exc:
            try:
                safe_body = exc.read(4096)
            except (AttributeError, OSError):
                safe_body = None
            return None, classify_http_error(exc.code, safe_body), exc.code
        except TimeoutError:
            return None, classify_openai_failure(error=TimeoutError()), None
        except (urllib.error.URLError, ConnectionError):
            return None, classify_openai_failure(error=urllib.error.URLError("network")), None
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
            return None, "INVALID_RESPONSE", None

    @staticmethod
    def _extract_content(body: dict[str, Any]) -> str:
        if isinstance(body.get("output_text"), str):
            return body["output_text"]
        output = body.get("output")
        if isinstance(output, list):
            parts = []
            for item in output:
                for part in item.get("content", []) if isinstance(item, dict) else []:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        parts.append(part["text"])
            if parts:
                return "".join(parts)
        raise KeyError("response content")

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
