from jafar.legal_entity_adapters import LegalEntitySourceRegistry, PublicSourceAdapter
from jafar.legal_entity_intelligence import EntityQuery


def test_registry_runs_all_public_adapters_and_preserves_failures():
    registry = LegalEntitySourceRegistry(
        [
            PublicSourceAdapter("kad", "https://kad.arbitr.ru/"),
            PublicSourceAdapter("fssp"),
        ]
    )

    results = registry.search_all(EntityQuery(inn="7701234567"))

    assert [item.source_key for item in results] == ["kad", "fssp"]
    assert all(item.status == "no_data" for item in results)


def test_registry_contains_only_registered_sources():
    registry = LegalEntitySourceRegistry([PublicSourceAdapter("egrul")])
    assert registry.keys() == ["egrul"]
