import pytest

from jafar.legal_position_service import LegalPositionReadService


class MatterStore:
    def get(self, matter_id): return {"id": matter_id}


class AnalysisRepo:
    def __init__(self, result): self.result = result
    def list_for_matter(self, matter_id): return [{"matter_id": matter_id, "document_id": None, "result": self.result}]


def read(result):
    return LegalPositionReadService(MatterStore(), AnalysisRepo(result)).get("m1")


def test_missing_issues_is_empty():
    assert read({}).items == []


def test_issues_are_reviewable_analysis_findings_without_sources():
    item = read({"issues": [{"title": "Risk", "description": "Проверить договор"}]}).items[0]
    assert item.kind == "analysis_finding"
    assert item.text == "Проверить договор"
    assert item.review_state == "needs_review"
    assert item.sources == []


def test_malformed_issues_fail_closed():
    with pytest.raises(TypeError): read({"issues": ["not-an-issue"]})
