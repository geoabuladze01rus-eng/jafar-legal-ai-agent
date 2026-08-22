from jafar.entity_investigation_pipeline import EntityInvestigationPipeline
from jafar.legal_entity_intelligence import EntityQuery, SourceFinding


class FakeSource:
    def __init__(self, key, finding):
        self.source_key = key
        self.finding = finding

    def lookup(self, query):
        return self.finding


def test_pipeline_runs_all_configured_sources_and_returns_auditable_report():
    sources = [
        FakeSource("egrul", SourceFinding("egrul", "found", "ЕГРЮЛ", {"name": "ООО Ромашка"}, confidence=0.99)),
        FakeSource("fssp", SourceFinding("fssp", "negative", "ФССП", {}, confidence=0.95)),
        FakeSource("kad", SourceFinding("kad", "found", "КАД", {"case_count": 2}, confidence=0.9)),
    ]
    report = EntityInvestigationPipeline(sources).run(EntityQuery(name=" ООО Ромашка "))
    assert report.query.name == "ООО Ромашка"
    assert report.source_order == ("egrul", "fssp", "kad")
    assert report.profile["sources_checked"] == 3
    assert report.profile["sources_negative"] == 1
