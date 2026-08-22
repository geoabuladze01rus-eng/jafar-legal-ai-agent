from jafar.entity_investigation_report import EntityInvestigationReportBuilder


def test_report_is_auditable_and_preserves_source_results():
    report = EntityInvestigationReportBuilder().build(
        subject={"name": "ООО Тест", "inn": "7701234567"},
        registry={"ogrn": "1027700000000", "status": "active"},
        source_results=[
            {"source": "fssp", "status": "negative"},
            {"source": "fns", "status": "found"},
        ],
        risks=[{"code": "debt", "severity": "high", "evidence": ["fssp"]}],
        checked_at="2026-08-21T18:00:00+03:00",
    ).to_dict()
    assert [item["source"] for item in report["sources"]] == ["fns", "fssp"]
    assert report["subject"]["inn"] == "7701234567"
    assert report["risks"][0]["code"] == "debt"
