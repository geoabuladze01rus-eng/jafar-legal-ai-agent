import json
import urllib.error

from jafar.domains import DocumentTask, MatterType
from jafar.legal_analysis import LegalAnalyzer
from jafar.legal_models import RiskLevel
from jafar.model_provider import GeminiProvider, OpenAICompatibleProvider


class StubProvider:
    def __init__(self, payload):
        self.payload = payload

    def analyze(self, text, task, matter_type):
        return self.payload


def test_model_result_is_validated_and_enriched():
    analyzer = LegalAnalyzer(
        provider=StubProvider(
            {
                "summary": "Модель нашла риск обжалования.",
                "issues": [
                    {
                        "title": "Обжалование",
                        "description": "Нужна проверка срока.",
                        "risk": "high",
                    }
                ],
                "deadlines": [],
                "key_facts": ["Суд упомянут."],
                "missing_information": [],
                "confidence": 0.91,
            }
        )
    )

    result = analyzer.analyze(
        "Постановление суда.", DocumentTask.LEGAL_ANALYSIS, MatterType.CRIMINAL
    )

    assert result.summary == "Модель нашла риск обжалования."
    assert result.issues[0].risk == RiskLevel.HIGH
    assert result.confidence == 0.91
    assert result.task == DocumentTask.LEGAL_ANALYSIS
    assert result.matter_type == MatterType.CRIMINAL


def test_invalid_model_result_falls_back_to_heuristics():
    analyzer = LegalAnalyzer(provider=StubProvider({"confidence": "not-a-number"}))

    result = analyzer.analyze(
        "Срок истекает 21.08.2026.", DocumentTask.LEGAL_ANALYSIS, MatterType.CIVIL
    )

    assert result.deadlines
    assert result.issues
    assert result.confidence == 0.55


def test_provider_json_parser_accepts_json_fence():
    payload = {
        "summary": "ok",
        "issues": [],
        "deadlines": [],
        "key_facts": [],
        "missing_information": [],
        "confidence": 0.8,
    }
    parsed = OpenAICompatibleProvider._parse_json(f"```json\n{json.dumps(payload)}\n```")
    assert parsed == payload


class _Response:
    def __init__(self, body): self.body = body if isinstance(body, bytes) else json.dumps(body).encode()
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, *_): return self.body
    def close(self): pass


def test_provider_uses_responses_contract_and_extracts_output_text():
    seen = {}
    def transport(request, timeout):
        seen.update(url=request.full_url, payload=json.loads(request.data))
        return _Response({"output_text": '{"summary":"ok"}'})
    result, category, status = OpenAICompatibleProvider("k", "gpt-test", transport=transport).analyze_with_diagnostics(
        "synthetic", DocumentTask.LEGAL_ANALYSIS, MatterType.CIVIL
    )
    assert result == {"summary": "ok"} and category is None and status is None
    assert seen["url"].endswith("/responses")
    assert "messages" not in seen["payload"]
    assert seen["payload"]["input"][0]["content"][0]["type"] == "input_text"


def test_provider_classifies_http_and_transport_failures():
    def fail(status, body=b""):
        def transport(request, timeout):
            raise urllib.error.HTTPError(request.full_url, status, "x", {}, _Response(body))
        return OpenAICompatibleProvider("k", "m", transport=transport).analyze_with_diagnostics("x", DocumentTask.LEGAL_ANALYSIS, MatterType.CIVIL)[1]
    assert fail(400) == "INVALID_REQUEST"
    assert fail(401) == "AUTHENTICATION"
    assert fail(404) == "MODEL_UNAVAILABLE"
    assert fail(429) == "RATE_LIMIT"
    assert fail(429, b'{"error":{"code":"insufficient_quota"}}') == "QUOTA_OR_BILLING"
    assert fail(500) == "PROVIDER_ERROR"

    def timeout(request, timeout): raise TimeoutError()
    assert OpenAICompatibleProvider("k", "m", transport=timeout).analyze_with_diagnostics("x", DocumentTask.LEGAL_ANALYSIS, MatterType.CIVIL)[1] == "TIMEOUT"

    def network(request, timeout): raise urllib.error.URLError("offline")
    assert OpenAICompatibleProvider("k", "m", transport=network).analyze_with_diagnostics("x", DocumentTask.LEGAL_ANALYSIS, MatterType.CIVIL)[1] == "NETWORK"


def test_gemini_generate_content_contract_is_synthetic_and_configured():
    seen = {}
    def transport(payload):
        seen.update(payload)
        return {"candidates": [{"content": {"parts": [{"text": '{"summary":"ok"}'}]}}]}
    provider = GeminiProvider(api_key="synthetic", model="configured-model", enabled=True, transport=transport)
    result, category, _ = provider.analyze_with_diagnostics("synthetic", DocumentTask.LEGAL_ANALYSIS, MatterType.CIVIL)
    assert result == {"summary": "ok"} and category is None
    assert seen["contents"][0]["parts"][0]["text"]
    assert GeminiProvider(api_key="synthetic", model="", enabled=True, transport=transport).analyze("x", DocumentTask.LEGAL_ANALYSIS, MatterType.CIVIL) is None
