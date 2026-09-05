from __future__ import annotations

import time
from dataclasses import dataclass

from openai import OpenAI

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


class OpenAILegalAnalyzer:
    """OpenAI provider used by Jafar's provider-agnostic model router."""

    key = "openai"

    def __init__(self, *, config: AIProviderConfig | None = None, client: OpenAI | None = None) -> None:
        self.config = config or AIProviderConfig()
        self.client = client or OpenAI(
            api_key=settings.openai_api_key,
            timeout=self.config.timeout_seconds,
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
                    raise RuntimeError("OpenAI returned no structured legal analysis")
                return response.output_parsed
            except ValueError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt >= self.config.max_retries:
                    break
                time.sleep(self.config.retry_backoff_seconds * (2**attempt))

        raise RuntimeError("OpenAI legal analysis failed after retries") from last_error

    def complete(self, request: ModelRequest) -> ModelResponse:
        try:
            task = DocumentTask(request.task)
        except ValueError:
            task = DocumentTask.SUMMARIZE

        try:
            matter_type = MatterType(request.matter_type) if request.matter_type else MatterType.GENERAL
        except ValueError:
            matter_type = MatterType.GENERAL

        analysis = self.analyze(text=request.prompt, task=task, matter_type=matter_type)
        return ModelResponse(
            provider=self.key,
            model=self.config.model,
            text=analysis.summary,
            metadata={"legal_analysis": analysis.model_dump(mode="json")},
        )
