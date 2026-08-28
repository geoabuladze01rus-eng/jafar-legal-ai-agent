from datetime import datetime, timezone

import pytest

from jafar.document_repository import SupabaseDocumentRepository


class Query:
    def __init__(self, rows=None, error=None): self.rows, self.error, self.calls = rows or [], error, []
    def select(self, fields): self.calls.append(("select", fields)); return self
    def eq(self, field, value): self.calls.append(("eq", field, value)); return self
    def order(self, field, desc=False): self.calls.append(("order", field, desc)); return self
    def execute(self):
        if self.error: raise self.error
        return type("Response", (), {"data": self.rows})()


class Client:
    def __init__(self, query): self.query_obj = query
    def table(self, name): assert name == "documents"; return self.query_obj


def test_document_repository_selects_safe_metadata_and_orders():
    query = Query([{"id": "d1", "matter_id": "m1", "filename": "a.pdf", "created_at": datetime.now(timezone.utc).isoformat(), "processing_status": "stored"}])
    docs = SupabaseDocumentRepository(Client(query)).list_for_matter("m1")
    assert docs[0].id == "d1"
    assert query.calls == [("select", "id,matter_id,filename,content_type,source,created_at,processing_status"), ("eq", "matter_id", "m1"), ("order", "created_at", True)]


def test_repository_propagates_query_failure():
    with pytest.raises(RuntimeError, match="database unavailable"):
        SupabaseDocumentRepository(Client(Query(error=RuntimeError("database unavailable")))).list_for_matter("m1")


def test_empty_result_is_distinct_from_failure():
    assert SupabaseDocumentRepository(Client(Query())).list_for_matter("m1") == []
