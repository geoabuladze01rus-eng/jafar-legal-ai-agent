from jafar.source_collector import SourceQuery
from jafar.sources.fns_egrul import FnsEgrulAdapter


class FakeTransport:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error

    def lookup(self, query):
        if self.error:
            raise self.error
        return self.value


def test_fns_adapter_returns_found():
    adapter = FnsEgrulAdapter(FakeTransport({"inn": "7701234567", "name": "ООО Тест"}))
    result = adapter.collect(SourceQuery(inn="7701234567"))
    assert result.status == "found"
    assert result.data["inn"] == "7701234567"


def test_fns_adapter_handles_timeout():
    adapter = FnsEgrulAdapter(FakeTransport(error=TimeoutError("timeout")))
    result = adapter.collect(SourceQuery(inn="7701234567"))
    assert result.status == "timeout"
