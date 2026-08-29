from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

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
    max_output_tokens: int = 6000

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("ai_provider_timeout_must_be_positive")
        if self.max_retries < 0 or self.max_retries > 5:
            raise ValueError("ai_provider_retries_out_of_range")
        if self.retry_backoff_seconds < 0:
            raise ValueError("ai_provider_retry_backoff_must_be_non_negative")
        if self.max_output_tokens <= 0 or self.max_output_tokens > 20_000:
            raise ValueError("ai_provider_max_output_tokens_out_of_range")


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
        analysis, _ = self.analyze_with_usage(
            text=text,
            task=task,
            matter_type=matter_type,
        )
        return analysis

    def analyze_with_usage(
        self,
        *,
        text: str,
        task: DocumentTask,
        matter_type: MatterType = MatterType.GENERAL,
    ) -> tuple[LegalAnalysis, dict[str, Any]]:
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
                    max_output_tokens=self.config.max_output_tokens,
                )
                if response.output_parsed is None:
                    raise RuntimeError("OpenAI returned no structured legal analysis")
                return response.output_parsed, self._safe_usage_metadata(response)
            except ValueError:
                raise
            except RuntimeError as exc:
                if str(exc) == "OpenAI returned no structured legal analysis":
                    # The provider may already have processed and billed the request. A missing
                    # structured response is not safe to retry automatically.
                    raise
                last_error = exc
                if attempt >= self.config.max_retries:
                    break
            except Exception as exc:  # noqa: BLE001
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

        analysis, metadata = self.analyze_with_usage(text=request.prompt, task=task)
        return ModelResponse(
            provider=self.key,
            model=self.config.model,
            text=analysis.summary,
            metadata=metadata,
        )

    @staticmethod
    def _safe_usage_metadata(response: Any) -> dict[str, Any]:
        """Expose numeric usage only; never copy structured legal output into metadata."""

        usage = getattr(response, "usage", None)
        if usage is None:
            return {}
        if hasattr(usage, "model_dump"):
            raw = usage.model_dump()
        elif isinstance(usage, dict):
            raw = usage
        else:
            raw = {
                key: getattr(usage, key)
                for key in (
                    "input_tokens",
                    "output_tokens",
                    "total_tokens",
                    "input_tokens_details",
                    "output_tokens_details",
                )
                if hasattr(usage, key)
            }
        sanitized = OpenAILegalAnalyzer._numeric_tree(raw)
        return {"usage": sanitized} if sanitized else {}

    @staticmethod
    def _numeric_tree(value: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(item, (int, float)) and not isinstance(item, bool):
                result[key] = item
            elif isinstance(item, dict):
                nested = OpenAILegalAnalyzer._numeric_tree(item)
                if nested:
                    result[key] = nested
        return result
