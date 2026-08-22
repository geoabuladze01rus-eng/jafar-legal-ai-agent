from jafar.entity_report import EntityReportEngine


def test_entity_report_merges_identity_and_risks():
    report = EntityReportEngine().build(
        query="ООО Ромашка",
        source_results=[
            {"source": "fns", "confidence": 0.9, "result": {"name": "ООО Ромашка", "inn": "7701234567"}},
            {"source": "fssp", "confidence": 0.7, "result": {"risk_flags": ["исполнительные производства"]}},
        ],
    )
    assert report.identity["inn"] == "7701234567"
    assert "исполнительные производства" in report.risk_flags
    assert report.confidence == 0.8
