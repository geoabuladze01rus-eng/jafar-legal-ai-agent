from jafar.source_collector import SourceCollector, SourceQuery, SourceResult


class FakeSource:
    def __init__(self, name, status="found"):
        self.name = name
        self.status = status

    def collect(self, query):
        return SourceResult(self.name, self.status, {"inn": query.inn})


class BrokenSource:
    name = "broken"

    def collect(self, query):
        raise RuntimeError("temporary failure")


def test_collector_keeps_partial_results_when_one_source_fails():
    results = SourceCollector([FakeSource("fns"), FakeSource("kad", "no_data"), BrokenSource()]).collect(SourceQuery(inn="7701234567"))
    assert [item.source for item in results] == ["broken", "fns", "kad"]
    assert results[0].status == "error"
    assert results[1].status == "found"
    assert results[2].status == "no_data"
