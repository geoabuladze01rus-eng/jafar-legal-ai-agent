import json

from jafar.domains import DocumentTask, MatterType
from jafar.legal_analysis import LegalAnalyzer
from jafar.model_provider import OpenAICompatibleProvider


def test_deterministic_analyzer_produces_bounded_review_candidate():
    analyzer = LegalAnalyzer()

    result = analyzer.analyze(
        "Постановление суда.", DocumentTask.LEGAL_ANALYSIS, MatterType.CRIMINAL
    )

    assert result.summary == "Постановление суда."
    assert result.confidence == 0.35
    assert result.task == DocumentTask.LEGAL_ANALYSIS
    assert result.matter_type == MatterType.CRIMINAL


def test_deterministic_analyzer_does_not_require_provider_configuration():
    analyzer = LegalAnalyzer()

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
