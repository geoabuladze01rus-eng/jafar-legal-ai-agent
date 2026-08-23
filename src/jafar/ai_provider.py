from __future__ import annotations

import os
from dataclasses import dataclass

from openai import OpenAI

from .domains import DocumentTask, MatterType
from .legal_models import LegalAnalysis
from .model_router import ModelRequest, ModelResponse


@dataclass(frozen=True)
class AIProviderConfig:
    model: str = "gpt-5.6"
    timeout_seconds: float = 60.0


class OpenAILegalAnalyzer:
    """OpenAI provider used by Jafar's provider-agnostic model router."""

    key = "openai"

    def __init__(self, *, config: AIProviderConfig, client: OpenAI | None = None) -> None:
        self.config = config
        self.client = client or OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            timeout=config.timeout_seconds,
        )

    def available(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY")) or self.client is not None

    def analyze(
        self,
        *,
        text: str,
        task: DocumentTask,
        matter_type: MatterType = MatterType.GENERAL,
    ) -> LegalAnalysis:
        if not text.strip():
            raise ValueError("document text must not be empty")

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
