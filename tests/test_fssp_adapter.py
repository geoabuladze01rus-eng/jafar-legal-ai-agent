from jafar.fssp_adapter import FsspPublicAdapter
from jafar.legal_entity_intelligence import EntityQuery
from jafar.public_source_transport import HttpResponse


class FakeTransport:
    def get(self, url):
        return HttpResponse(200, '{"proceedings":[]}', url)


def test_fssp_adapter_normalizes_public_response():
    adapter = FsspPublicAdapter(
        FakeTransport(),
        lambda query: f"https://example.test/fssp?q={query.value}",
    )
    result = adapter.search(EntityQuery(inn="7701234567"))
    assert result.source_key == "fssp"
    assert result.status == "found"
    assert result.data["raw_text"]
