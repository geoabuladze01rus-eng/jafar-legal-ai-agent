import json

from jafar.domains import DocumentTask, MatterType
from jafar.legal_analysis import LegalAnalyzer
from jafar.legal_models import RiskLevel
from jafar.model_provider import OpenAICompatibleProvider


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
