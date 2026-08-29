from __future__ import annotations

from pathlib import Path

from jafar.telegram_editorial import safety_check


def test_editorial_auto_requires_low_risk_and_documented_core_boundary() -> None:
    assert safety_check("общий профессиональный вывод")["auto_publish_allowed"] is True
    assert safety_check("паспорт доверителя")["auto_publish_allowed"] is False
    document = Path("docs/TELEGRAM_CORE_INTEGRATION.md").read_text(encoding="utf-8")
    assert "CostRuntime" in document
    assert "ApprovalExecutionService" in document
    assert "delivery_uncertain" in document


def test_current_editorial_layer_has_no_direct_ai_client() -> None:
    source = Path("src/jafar/telegram_editorial.py").read_text(encoding="utf-8")
    assert "OpenAI" not in source
    assert "httpx" not in source
