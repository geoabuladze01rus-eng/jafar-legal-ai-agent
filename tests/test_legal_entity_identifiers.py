import pytest

from jafar.legal_entity_intelligence import (
    EntityQuery,
    LegalEntityIntelligence,
    valid_inn,
    valid_kpp,
    valid_ogrn,
)


def test_valid_inn_control_digits_for_legal_entity_and_individual() -> None:
    assert valid_inn("7707083893") is True
    assert valid_inn("500100732259") is True


def test_invalid_inn_control_digits_fail_closed() -> None:
    assert valid_inn("7701234567") is False
    assert valid_inn("500100732258") is False

    with pytest.raises(ValueError, match="invalid_inn"):
        EntityQuery("7701234567", "inn")
    with pytest.raises(ValueError, match="invalid_inn"):
        EntityQuery.infer("7701234567")


def test_valid_ogrn_and_ogrnip_control_digits() -> None:
    assert valid_ogrn("1027700132195") is True
    assert valid_ogrn("304500116000157") is True


def test_invalid_ogrn_control_digits_fail_closed() -> None:
    assert valid_ogrn("1027700132194") is False
    assert valid_ogrn("304500116000156") is False

    with pytest.raises(ValueError, match="invalid_ogrn"):
        EntityQuery.infer("1027700132194")


def test_kpp_accepts_structural_alphanumeric_reason_code() -> None:
    assert valid_kpp("7707AA001") is True
    query = EntityQuery("7707aa001", "kpp")
    assert query.value == "7707AA001"
    assert query.query_type == "kpp"


def test_invalid_kpp_structure_is_rejected() -> None:
    assert valid_kpp("77AA01001") is False
    with pytest.raises(ValueError, match="invalid_kpp"):
        EntityQuery("77AA01001", "kpp")


def test_entity_source_exception_text_is_not_exposed() -> None:
    class LeakySource:
        source_key = "registry"

        def lookup(self, query):
            raise RuntimeError("Authorization: Bearer super-secret-token")

    profile = LegalEntityIntelligence([LeakySource()]).investigate(
        EntityQuery("ООО Ромашка", "name")
    )

    details = profile["findings"][0]["details"]
    assert details == {"reason": "source_lookup_failed", "type": "RuntimeError"}
    assert "super-secret-token" not in str(profile)
