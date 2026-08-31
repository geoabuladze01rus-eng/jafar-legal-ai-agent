from jafar.fns_adapter import FnsPublicAdapter
from jafar.legal_entity_adapters import EntityQuery
from jafar.public_source_transport import HttpResponse


class FakeTransport:
    def get(self, url):
        return HttpResponse(200, '{"inn":"7701234567"}', url)


def test_fns_adapter_returns_source_result():
    adapter = FnsPublicAdapter(
        FakeTransport(),
        lambda query: f"https://example.test/fns?q={query.value}",
    )
    result = adapter.search(EntityQuery(inn="7701234567"))
    assert result.source_key == "egrul"
    assert result.status == "found"
    assert result.data["raw_text"]
