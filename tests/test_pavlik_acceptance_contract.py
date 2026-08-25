from jafar.legal_reasoning import LegalReasoningEngine

MAIN_CASE = "12604008104000012"


def test_pavlik_reasoning_preserves_provenance_attribution_and_review_gate():
    evidence = [
        {"evidence_id": "p1-case", "page": 1, "source": "court_ruling"},
        {"evidence_id": "p2-merge", "page": 2, "source": "court_ruling"},
        {"evidence_id": "p4-allegation", "page": 4, "source": "investigation_allegation"},
        {"evidence_id": "p5-outcome", "page": 5, "source": "court_conclusion"},
    ]
    facts = [
        {
            "statement": f"Основной номер уголовного дела: {MAIN_CASE}",
            "evidence_ids": ["p1-case"],
            "confidence": 0.99,
            "source_type": "document_fact",
        },
        {
            "statement": "09.04.2026 дела объединены под основным номером",
            "evidence_ids": ["p2-merge"],
            "confidence": 0.98,
            "source_type": "document_fact",
        },
        {
            "statement": "Следствие утверждает наличие организованной преступной деятельности",
            "evidence_ids": ["p4-allegation"],
            "confidence": 0.80,
            "source_type": "investigation_allegation",
        },
        {
            "statement": "В поврежденном OCR-фрагменте встречается фамилия Хафизов А.А.",
            "evidence_ids": ["missing-evidence"],
            "confidence": 0.45,
            "source_type": "evidence_gap",
        },
        {
            "statement": "Суд избрал домашний арест по 03.08.2026",
            "evidence_ids": ["p5-outcome"],
            "confidence": 0.99,
            "source_type": "court_conclusion",
        },
    ]
    timeline = [
        {"event_at": "2026-06-27", "title": "Домашний арест"},
        {"event_at": "2026-03-03", "title": "Возбуждение основного дела"},
        {"event_at": "2026-04-09", "title": "Объединение производств"},
        {"event_at": "2026-06-25T16:20:00", "title": "Задержание"},
    ]

    result = LegalReasoningEngine().analyze(
        facts=facts,
        evidence=evidence,
        risks=[
            {
                "statement": "Не повышать утверждения следствия до нейтрально установленных фактов",
                "severity": "high",
                "evidence_ids": ["p4-allegation"],
                "confidence": 0.99,
                "source_type": "review_rule",
            }
        ],
        timeline=timeline,
    )

    assert result["human_review_required"] is True
    assert result["evidence_count"] == 4
    assert [event["title"] for event in result["timeline"]] == [
        "Возбуждение основного дела",
        "Объединение производств",
        "Задержание",
        "Домашний арест",
    ]

    findings = result["findings"]
    main_case = next(item for item in findings if MAIN_CASE in item["statement"])
    allegation = next(item for item in findings if "Следствие утверждает" in item["statement"])
    evidence_gap = next(item for item in findings if "Хафизов" in item["statement"])
    court_outcome = next(item for item in findings if "домашний арест" in item["statement"])
    risk = next(item for item in findings if item["kind"] == "risk_signal")

    assert main_case["basis"] == ["p1-case"]
    assert main_case["requires_human_review"] is False
    assert main_case["metadata"]["source_type"] == "document_fact"

    assert allegation["basis"] == ["p4-allegation"]
    assert allegation["requires_human_review"] is True
    assert allegation["confidence"] == 0.80
    assert allegation["metadata"]["source_type"] == "investigation_allegation"

    assert evidence_gap["basis"] == []
    assert evidence_gap["requires_human_review"] is True
    assert evidence_gap["confidence"] == 0.45
    assert evidence_gap["metadata"]["source_type"] == "evidence_gap"
    assert evidence_gap["metadata"]["evidence_gap"] is True

    assert court_outcome["metadata"]["source_type"] == "court_conclusion"

    assert risk["basis"] == ["p4-allegation"]
    assert risk["requires_human_review"] is True
    assert risk["metadata"]["severity"] == "high"
    assert risk["metadata"]["source_type"] == "review_rule"


def test_malformed_confidence_fails_closed_without_crashing_legal_analysis():
    result = LegalReasoningEngine().analyze(
        facts=[
            {
                "statement": "Поврежденный ответ модели",
                "evidence_ids": ["p3"],
                "confidence": "unknown",
                "source_type": "document_fact",
            },
            {
                "statement": "NaN не должен стать высоким confidence",
                "evidence_ids": ["p3"],
                "confidence": float("nan"),
                "source_type": "document_fact",
            },
        ],
        evidence=[{"evidence_id": "p3", "page": 3}],
        risks=[
            {
                "statement": "Поврежденный confidence риска",
                "severity": "high",
                "evidence_ids": ["missing"],
                "confidence": None,
                "source_type": "review_rule",
            }
        ],
    )

    first, second, risk = result["findings"]

    assert first["confidence"] == 0.0
    assert first["requires_human_review"] is True
    assert first["metadata"]["confidence_invalid"] is True

    assert second["confidence"] == 0.0
    assert second["requires_human_review"] is True
    assert second["metadata"]["confidence_invalid"] is True

    assert risk["confidence"] == 0.0
    assert risk["requires_human_review"] is True
    assert risk["basis"] == []
    assert risk["metadata"]["confidence_invalid"] is True
    assert risk["metadata"]["evidence_gap"] is True


def test_confidence_is_clamped_to_legal_contract_bounds():
    result = LegalReasoningEngine().analyze(
        facts=[
            {
                "statement": "Сверх единицы",
                "evidence_ids": ["e1"],
                "confidence": 9.0,
                "source_type": "document_fact",
            },
            {
                "statement": "Ниже нуля",
                "evidence_ids": ["e1"],
                "confidence": -4.0,
                "source_type": "document_fact",
            },
        ],
        evidence=[{"evidence_id": "e1"}],
    )

    high, low = result["findings"]
    assert high["confidence"] == 1.0
    assert low["confidence"] == 0.0
    assert low["requires_human_review"] is True
