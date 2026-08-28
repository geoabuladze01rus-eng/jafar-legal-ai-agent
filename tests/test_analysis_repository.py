from jafar.legal_position_service import SupabaseAnalysisRepository


class Query:
    def __init__(self): self.calls=[]
    def select(self, value): self.calls.append(("select", value)); return self
    def eq(self, *value): self.calls.append(("eq", *value)); return self
    def order(self, *value, **kwargs): self.calls.append(("order", value, kwargs)); return self
    def execute(self): return type("R", (), {"data": []})()
class Client:
    def __init__(self, q): self.q=q
    def table(self, name): assert name == "ai_analyses"; return self.q

def test_analysis_repository_is_explicit_read_only_query():
    q=Query(); assert SupabaseAnalysisRepository(Client(q)).list_for_matter("m1") == []
    assert q.calls[0] == ("select", "id,matter_id,document_id,result,source_chunks,created_at,requires_lawyer_review,review_status")
    assert ("eq", "matter_id", "m1") in q.calls
