from jafar.entity_investigation_pipeline import EntityInvestigationPipeline
from jafar.legal_entity_adapters import LegalEntitySourceRegistry, SourceResult
from jafar.legal_entity_intelligence import EntityQuery


class FakeSource:
    def __init__(self, key, result):
        self.source_key = key
        self.result = result

    def search(self, query):
        return self.result


def test_pipeline_runs_all_configured_sources_and_returns_auditable_report():
    registry = LegalEntitySourceRegistry(
        [
            FakeSource("egrul", SourceResult("egrul", "found", data={"name": "ООО Ромашка"})),
            FakeSource("fssp", SourceResult("fssp", "no_data", data={})),
            FakeSource("kad", SourceResult("kad", "found", data={"case_count": 2})),
        ]
    )
    report = EntityInvestigationPipeline(registry).run(EntityQuery(name=" ООО Ромашка "))
    assert report.query.name == "ООО Ромашка"
    assert tuple(item.source_key for item in report.results) == ("egrul", "fssp", "kad")
    assert report.successful_sources == 2
    assert report.failed_sources == 0
