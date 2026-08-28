import pytest

from jafar.legal_entity_adapters import (
    LegalEntitySourceRegistry,
    PublicSourceAdapter,
    PublicUrlSourceAdapter,
)
from jafar.legal_entity_intelligence import EntityQuery


def test_registry_runs_all_public_adapters_and_preserves_failures():
    registry = LegalEntitySourceRegistry(
        [
            PublicSourceAdapter("kad", "https://kad.arbitr.ru/"),
            PublicSourceAdapter("fssp"),
        ]
    )

    results = registry.search_all(EntityQuery("7701234567", "inn"))

    assert [item.source_key for item in results] == ["kad", "fssp"]
    assert all(item.status == "no_data" for item in results)


def test_registry_contains_only_registered_sources():
    registry = LegalEntitySourceRegistry([PublicSourceAdapter("egrul")])
    assert registry.keys() == ["egrul"]


def test_registry_rejects_duplicate_source_keys_instead_of_shadowing():
    with pytest.raises(ValueError, match="duplicate_legal_entity_source_key"):
        LegalEntitySourceRegistry(
            [PublicSourceAdapter("kad"), PublicSourceAdapter("KAD")]
        )


def test_public_url_template_requires_safe_http_destination():
    with pytest.raises(ValueError, match="single_query_placeholder"):
        PublicUrlSourceAdapter("kad", "https://kad.arbitr.ru/")

    with pytest.raises(ValueError, match="localhost_forbidden"):
        PublicUrlSourceAdapter("kad", "http://localhost/search?q={query}")

    with pytest.raises(ValueError, match="private_address_forbidden"):
        PublicUrlSourceAdapter("kad", "http://127.0.0.1/search?q={query}")

    with pytest.raises(ValueError, match="http_or_https"):
        PublicUrlSourceAdapter("kad", "file:///tmp/{query}")


def test_public_url_adapter_percent_encodes_user_query():
    adapter = PublicUrlSourceAdapter(
        "kad",
        "https://kad.arbitr.ru/Search?text={query}",
    )

    result = adapter.search(EntityQuery("ООО Ромашка & сын", "name"))

    assert result.source_url is not None
    assert "ООО" not in result.source_url
    assert "%26" in result.source_url
    assert result.source_url.startswith("https://kad.arbitr.ru/Search?text=")


def test_registry_marks_adapter_source_identity_mismatch_as_error():
    class WrongIdentityAdapter:
        source_key = "kad"

        def search(self, query):
            return type(
                "Result",
                (),
                {
                    "source_key": "fssp",
                    "status": "found",
                    "source_url": None,
                    "data": {},
                    "error": None,
                },
            )()

    result = LegalEntitySourceRegistry([WrongIdentityAdapter()]).search_all(
        EntityQuery("7701234567", "inn")
    )[0]

    assert result.source_key == "kad"
    assert result.status == "error"
    assert "adapter_source_key_mismatch" in (result.error or "")
