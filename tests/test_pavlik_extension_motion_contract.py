from jafar.legal_reasoning import LegalReasoningEngine


def test_extension_motion_preserves_request_vs_court_and_allegation_review_gate():
    evidence = [
        {"evidence_id": "ext-p1-procedure", "page": 1, "source": "investigator_motion"},
        {"evidence_id": "ext-p2-allegation", "page": 2, "source": "investigator_motion"},
        {"evidence_id": "ext-p2-investigation-term", "page": 2, "source": "investigator_motion"},
        {"evidence_id": "ext-p3-status", "page": 3, "source": "investigator_motion"},
        {"evidence_id": "ext-p4-request", "page": 4, "source": "investigator_motion"},
    ]
    facts = [
        {
            "statement": "Документ от 28.07.2026 является ходатайством следователя о продлении домашнего ареста",
            "evidence_ids": ["ext-p1-procedure"],
            "confidence": 0.99,
            "source_type": "document_fact",
        },
        {
            "statement": "Срок предварительного следствия в документе указан до 03.09.2026",
            "evidence_ids": ["ext-p2-investigation-term"],
            "confidence": 0.99,
            "source_type": "document_fact",
        },
        {
            "statement": "Следователь просит продлить домашний арест до 03.09.2026",
            "evidence_ids": ["ext-p4-request"],
            "confidence": 0.99,
            "source_type": "investigation_request",
            "metadata": {"is_court_decision": False},
        },
        {
            "statement": "Следствие утверждает наличие организованной преступной деятельности",
            "evidence_ids": ["ext-p2-allegation"],
            "confidence": 0.99,
            "source_type": "investigation_allegation",
        },
        {
            "statement": "Следствие утверждает значительный объём транспортных средств и неуплату таможенных платежей",
            "evidence_ids": ["ext-p2-allegation"],
            "confidence": 0.99,
            "source_type": "investigation_allegation",
        },
    ]
    timeline = [
        {"event_at": "2026-07-28", "title": "Ходатайство следователя о продлении"},
        {"event_at": "2026-06-25T16:20:00", "title": "Задержание"},
        {"event_at": "2026-06-27", "title": "Первоначальный домашний арест"},
        {"event_at": "2026-07-01", "title": "Предъявление обвинения"},
        {"event_at": "2026-07-07", "title": "Соединение дополнительных производств"},
        {"event_at": "2026-07-22", "title": "Продление срока следствия"},
    ]

    result = LegalReasoningEngine().analyze(
        facts=facts,
        evidence=evidence,
        timeline=timeline,
    )

    assert result["human_review_required"] is True
    assert [event["title"] for event in result["timeline"]] == [
        "Задержание",
        "Первоначальный домашний арест",
        "Предъявление обвинения",
        "Соединение дополнительных производств",
        "Продление срока следствия",
        "Ходатайство следователя о продлении",
    ]

    findings = result["findings"]
    motion_type = next(item for item in findings if "является ходатайством" in item["statement"])
    request = next(item for item in findings if "просит продлить" in item["statement"])
    allegations = [
        item
        for item in findings
        if item["metadata"].get("source_type") == "investigation_allegation"
    ]

    assert motion_type["metadata"]["source_type"] == "document_fact"
    assert motion_type["requires_human_review"] is False

    assert request["metadata"]["source_type"] == "investigation_request"
    assert request["metadata"]["is_court_decision"] is False
    assert request["confidence"] == 0.99
    assert request["requires_human_review"] is True

    assert len(allegations) == 2
    assert all(item["confidence"] == 0.99 for item in allegations)
    assert all(item["requires_human_review"] is True for item in allegations)


def test_extension_motion_keeps_historical_position_and_source_anomalies_explicit():
    evidence = [
        {"evidence_id": "ext-p2-history", "page": 2, "source": "investigator_motion"},
        {"evidence_id": "ext-p3-history", "page": 3, "source": "investigator_motion"},
    ]
    facts = [
        {
            "statement": "Документ фиксирует признание вины на более ранних процессуальных этапах",
            "evidence_ids": ["ext-p2-history", "ext-p3-history"],
            "confidence": 0.99,
            "source_type": "investigation_recorded_statement",
            "metadata": {
                "historical_position": True,
                "current_position": False,
            },
        },
        {
            "statement": "В источнике расходятся инициалы одного из участников",
            "confidence": 0.80,
            "source_type": "evidence_gap",
            "metadata": {"anomaly_code": "participant_initials_conflict"},
        },
        {
            "statement": "Один участник повторён в перечне предполагаемых участников",
            "confidence": 0.80,
            "source_type": "evidence_gap",
            "metadata": {"anomaly_code": "duplicate_participant_in_source"},
        },
        {
            "statement": "Одна фраза об органе, пресёкшем действия, обрывается в источнике",
            "confidence": 0.80,
            "source_type": "evidence_gap",
            "metadata": {"anomaly_code": "truncated_source_sentence"},
        },
    ]

    result = LegalReasoningEngine().analyze(facts=facts, evidence=evidence)

    findings = result["findings"]
    historical = findings[0]
    anomalies = findings[1:]

    assert historical["basis"] == ["ext-p2-history", "ext-p3-history"]
    assert historical["metadata"]["historical_position"] is True
    assert historical["metadata"]["current_position"] is False
    assert historical["metadata"]["source_type"] == "investigation_recorded_statement"
    assert historical["requires_human_review"] is True

    assert {item["metadata"]["anomaly_code"] for item in anomalies} == {
        "participant_initials_conflict",
        "duplicate_participant_in_source",
        "truncated_source_sentence",
    }
    assert all(item["basis"] == [] for item in anomalies)
    assert all(item["metadata"]["source_type"] == "evidence_gap" for item in anomalies)
    assert all(item["metadata"]["evidence_gap"] is True for item in anomalies)
    assert all(item["requires_human_review"] is True for item in anomalies)
    assert len(result["evidence_gaps"]) == 3
