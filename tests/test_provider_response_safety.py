import pytest

from jafar.gemini_provider import GeminiProvider
from jafar.model_providers import HTTPModelProvider, OpenAIResponsesProvider, safe_provider_metadata


def test_safe_provider_metadata_excludes_generated_content() -> None:
    metadata = safe_provider_metadata(
        {
            "id": "resp-1",
            "model": "model-a",
            "choices": [{"message": {"content": "privileged legal text"}}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "prompt_tokens_details": {"cached_tokens": 3},
            },
        }
    )

    assert metadata["id"] == "resp-1"
    assert metadata["usage"]["prompt_tokens"] == 10
    assert metadata["usage"]["prompt_tokens_details"]["cached_tokens"] == 3
    assert "choices" not in metadata
    assert "privileged legal text" not in repr(metadata)


def test_compatible_provider_fails_closed_on_unknown_response_shape() -> None:
    with pytest.raises(RuntimeError, match="no recognizable assistant text"):
        HTTPModelProvider._extract_text({"unexpected": "payload"})


def test_openai_responses_parser_extracts_nested_output_text() -> None:
    text = OpenAIResponsesProvider._extract_text(
        {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "Проверенный ответ"},
                    ],
                }
            ]
        }
    )
    assert text == "Проверенный ответ"


def test_openai_responses_parser_never_returns_raw_payload() -> None:
    with pytest.raises(RuntimeError, match="no recognizable output text"):
        OpenAIResponsesProvider._extract_text({"error": {"message": "internal"}})


def test_gemini_metadata_excludes_candidates_and_text() -> None:
    data = {
        "candidates": [{"content": {"parts": [{"text": "secret answer"}]}}],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20},
        "modelVersion": "gemini-test",
        "responseId": "r-1",
    }
    metadata = GeminiProvider._safe_metadata(data)

    assert metadata["usage"]["promptTokenCount"] == 10
    assert metadata["model_version"] == "gemini-test"
    assert "candidates" not in metadata
    assert "secret answer" not in repr(metadata)
