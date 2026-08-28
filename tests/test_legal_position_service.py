from types import SimpleNamespace

import pytest

from jafar.legal_position_service import LegalPositionReadService


class MatterStore:
    def get(self, value): return object() if value in {"a", "b"} else None
class AnalysisRepo:
    def __init__(self, rows): self.rows=rows
    def list_for_matter(self, _): return self.rows
class Docs:
    def __init__(self, rows): self.rows=rows
    def get(self, value): return self.rows.get(value)

def svc(rows, docs=None): return LegalPositionReadService(MatterStore(), AnalysisRepo(rows), Docs(docs or {"da": SimpleNamespace(matter_id="a")}))
def test_valid_multiple_gaps_and_review_safety():
    result=svc([{"matter_id":"a","document_id":"da","result":{"missing_information":["Gap A","Gap B"]}}]).get("a")
    assert [i.text for i in result.items] == ["Gap A","Gap B"]
    assert all(i.review_state == "needs_review" and i.sources == [] for i in result.items)
def test_analysis_mismatch_and_document_mismatch_rejected():
    with pytest.raises(ValueError): svc([{"matter_id":"b","document_id":"da","result":{}}]).get("a")
    with pytest.raises(ValueError): svc([{"matter_id":"a","document_id":"db","result":{}}], {"db": SimpleNamespace(matter_id="b")}).get("a")
def test_missing_or_malformed_result_rejected():
    assert svc([]).get("a").items == []
    assert svc([{"matter_id":"a","document_id":"da","result":{}}]).get("a").items == []
    with pytest.raises(ValueError): svc([{"matter_id":"a","document_id":"da","result":{"missing_information":["ok", 1]}}]).get("a")
