from jafar.legal_entity_adapters import LegalEntitySourceRegistry, PublicSourceAdapter
from jafar.legal_entity_research import EntityQuery, LegalEntityResearchService


def test_research_builds_auditable_profile_from_registered_sources():
    service = LegalEntityResearchService(
        registry=LegalEntitySourceRegistry(
            [
                PublicSourceAdapter("kad", "https://kad.arbitr.ru/"),
                PublicSourceAdapter("fssp"),
            ]
        )
    )

    report = service.research(EntityQuery("7707083893", "inn"))

    assert report.query.value == "7707083893"
    assert report.profile["sources_checked"] == 2
    assert report.profile["risk_level"] == "unknown"
    assert all(item.status == "no_data" for item in report.results)
