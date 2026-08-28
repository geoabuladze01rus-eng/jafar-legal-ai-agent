from jafar.domains import DocumentTask, MatterType
from jafar.model_provider import GeminiProvider


def test_gemini_contract_uses_configured_model_and_normalizes_response():
    seen = []
    provider = GeminiProvider(model="configured-model", enabled=True, transport=lambda request: seen.append(request) or {"text": '{"summary":"synthetic"}'})
    assert provider.analyze("synthetic", DocumentTask.LEGAL_ANALYSIS, MatterType.GENERAL) == {"summary": "synthetic"}
    assert seen[0]["model"] == "configured-model"


def test_gemini_is_disabled_without_explicit_transport():
    assert GeminiProvider(model="configured-model").analyze("x", DocumentTask.SUMMARIZE, MatterType.GENERAL) is None
