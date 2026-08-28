from types import SimpleNamespace

from jafar.ai_provider import OpenAILegalAnalyzer


class UsageObject:
    def model_dump(self):
        return {
            "input_tokens": 1200,
            "output_tokens": 300,
            "input_tokens_details": {"cached_tokens": 800},
            "non_numeric_vendor_detail": "drop-me",
        }


def test_openai_usage_metadata_contains_only_numeric_usage_tree() -> None:
    response = SimpleNamespace(
        usage=UsageObject(),
        output_parsed={"confidential": "legal analysis must not leak here"},
    )

    metadata = OpenAILegalAnalyzer._safe_usage_metadata(response)

    assert metadata == {
        "usage": {
            "input_tokens": 1200,
            "output_tokens": 300,
            "input_tokens_details": {"cached_tokens": 800},
        }
    }
    assert "output_parsed" not in metadata


def test_openai_usage_metadata_fails_to_empty_when_usage_absent() -> None:
    assert OpenAILegalAnalyzer._safe_usage_metadata(SimpleNamespace(usage=None)) == {}
