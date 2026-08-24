from __future__ import annotations

import random
import time
from dataclasses import dataclass

from openai import APIConnectionError, APIStatusError, OpenAI

from .config import settings
from .domains import DocumentTask, MatterType
from .legal_models import LegalAnalysis
from .model_router import ModelRequest, ModelResponse


@dataclass(frozen=True)
class AIProviderConfig:
    model: str = settings.model_name
    timeout_seconds: float = 60.0
    max_retries: int = 2
    retry_backoff_seconds: float = 0.5
    max_retry_delay_seconds: float = 8.0

    def __post_init__(self) -> None:
        if not 0 <= self.max_retries <= 10:
            raise ValueError("max_retries must be between 0 and 10")
        if self.retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds must not be negative")
        if self.max_retry_delay_seconds <= 0:
            raise ValueError("max_retry_delay_seconds must be positive")


class StructuredOutputError(RuntimeError):
    """The provider response did not satisfy the structured legal contract."""


class OpenAILegalAnalyzer:
    """OpenAI provider used by Jafar's provider-agnostic model router."""

    key = "openai"

    def __init__(self, *, config: AIProviderConfig | None = None, client: OpenAI | None = None) -> None:
        self.config = config or AIProviderConfig()
        self.client = client or OpenAI(
            api_key=settings.openai_api_key,
            timeout=self.config.timeout_seconds,
            max_retries=0,
        )

    def available(self) -> bool:
        return bool(settings.openai_api_key)

    def analyze(
        self,
        *,
        text: str,
        task: DocumentTask,
        matter_type: MatterType = MatterType.GENERAL,
    ) -> LegalAnalysis:
        if not text.strip():
            raise ValueError("document text must not be empty")

        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.client.responses.parse(
                    model=self.config.model,
                    input=[
                        {
                            "role": "system",
                            "content": (
                                "You are Jafar, a legal document analysis assistant. "
                                "Extract only information supported by the supplied document. "
                                "Do not invent facts, authorities, deadlines, or citations. "
                                "If information is missing or uncertain, state that explicitly. "
                                "Use the requested task and matter type when structuring the analysis."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Task: {task.value}\nMatter type: {matter_type.value}\n\n"
                                "Analyze the following document:\n\n" + text
                            ),
                        },
                    ],
                    text_format=LegalAnalysis,
                )
                if response.output_parsed is None:
                    raise StructuredOutputError("OpenAI returned no structured legal analysis")
                return response.output_parsed
            except ValueError:
                raise
            except Exception as exc:
                last_error = exc
                if not self._is_retryable(exc) or attempt >= self.config.max_retries:
                    if isinstance(exc, StructuredOutputError):
                        raise
                    break
                time.sleep(self._retry_delay(exc, attempt))

        raise RuntimeError("OpenAI legal analysis failed after retries") from last_error

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if isinstance(exc, APIConnectionError):
            return True
        if isinstance(exc, APIStatusError):
            return exc.status_code in {408, 409, 429} or exc.status_code >= 500
        return False

    def _retry_delay(self, exc: Exception, attempt: int) -> float:
        if isinstance(exc, APIStatusError):
            retry_after = exc.response.headers.get("retry-after")
            if retry_after:
                try:
                    return min(float(retry_after), self.config.max_retry_delay_seconds)
                except ValueError:
                    pass
        ceiling = min(
            self.config.retry_backoff_seconds * (2**attempt),
            self.config.max_retry_delay_seconds,
        )
        return random.uniform(0, ceiling)

    def complete(self, request: ModelRequest) -> ModelResponse:
        try:
            task = DocumentTask(request.task)
        except ValueError:
            task = DocumentTask.SUMMARIZE

        analysis = self.analyze(text=request.prompt, task=task)
        return ModelResponse(
            provider=self.key,
            model=self.config.model,
            text=analysis.summary,
            metadata={"legal_analysis": analysis.model_dump(mode="json")},
        )
