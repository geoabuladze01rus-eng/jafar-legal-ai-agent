from datetime import date

from fastapi.testclient import TestClient

from jafar.domains import DocumentTask, MatterType
from jafar.legal_analysis import LegalAnalyzer
from jafar.main import app


def test_analyzer_extracts_case_number_and_date() -> None:
    text = "По делу № А40-12345/2026 срок обжалования до 25.08.2026."
    result = LegalAnalyzer().analyze(text, DocumentTask.LEGAL_ANALYSIS, MatterType.ARBITRATION)

    assert "Номер дела/производства: А40-12345/2026" in result.key_facts
    assert any(deadline.due_date == date(2026, 8, 25) for deadline in result.deadlines)
    assert any(issue.title == "Обжалование" for issue in result.issues)


def test_matter_lifecycle_and_analysis_endpoint() -> None:
    client = TestClient(app)
    created = client.post(
        "/v1/matters",
        json={"title": "Тестовое дело", "matter_type": "civil", "case_number": "2-123/2026"},
    )
    assert created.status_code == 201
    matter_id = created.json()["id"]

    analyzed = client.post(
        "/v1/analyze",
        json={
            "matter_id": matter_id,
            "matter_type": "civil",
            "text": "Срок исполнения до 31.08.2026. Договор не исполнен.",
        },
    )
    assert analyzed.status_code == 200
    assert analyzed.json()["matter_id"] == matter_id
    assert analyzed.json()["analysis"]["deadlines"]

    fetched = client.get(f"/v1/matters/{matter_id}")
    assert fetched.status_code == 200
    assert fetched.json()["deadlines"]
