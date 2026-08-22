from jafar.entity_investigation import EntityInvestigation


def test_entity_investigation_plans_all_open_sources():
    plan = EntityInvestigation().plan(query="ООО Ромашка", inn="7701234567")
    types = {item.source_type for item in plan}
    assert "fns_egrul" in types
    assert "fssp" in types
    assert "kad" in types
    assert "fedresurs" in types
    assert "checko" in types
    assert "financial_reporting" in types


def test_entity_investigation_merges_source_statuses():
    result = EntityInvestigation.merge_results([
        {"status": "success"},
        {"status": "error"},
    ])
    assert result["sources_checked"] == 2
    assert result["successful_sources"] == 1
