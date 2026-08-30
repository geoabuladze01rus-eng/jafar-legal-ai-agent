import pytest

from jafar.legal_entity_intelligence import EntityQuery


def test_entity_query_supports_current_value_type_shape() -> None:
    query = EntityQuery("7707083893", "inn")

    assert query.value == "7707083893"
    assert query.query_type == "inn"
    assert query.inn == "7707083893"
    assert query.name is None


def test_entity_query_supports_legacy_keyword_identifier_shape() -> None:
    query = EntityQuery(ogrn="1027700132195")

    assert query.value == "1027700132195"
    assert query.query_type == "ogrn"
    assert query.ogrn == "1027700132195"


def test_entity_query_rejects_ambiguous_identifiers() -> None:
    with pytest.raises(ValueError, match="single_identifier"):
        EntityQuery(inn="7707083893", ogrn="1027700132195")

    with pytest.raises(ValueError, match="ambiguous_input"):
        EntityQuery("ООО Ромашка", "name", inn="7707083893")


def test_entity_query_rejects_structurally_invalid_numeric_identifiers() -> None:
    with pytest.raises(ValueError, match="invalid_inn"):
        EntityQuery("123", "inn")
    with pytest.raises(ValueError, match="invalid_ogrn"):
        EntityQuery("1234567890", "ogrn")
    with pytest.raises(ValueError, match="invalid_kpp"):
        EntityQuery("12345", "kpp")


def test_entity_query_inference_handles_russian_identifier_lengths() -> None:
    assert EntityQuery.infer("7707083893").query_type == "inn"
    assert EntityQuery.infer("500100732259").query_type == "inn"
    assert EntityQuery.infer("1027700132195").query_type == "ogrn"
    assert EntityQuery.infer("304500116000157").query_type == "ogrn"
    assert EntityQuery.infer("770701001").query_type == "kpp"
    assert EntityQuery.infer("ООО Ромашка").query_type == "name"
