from jafar.calendar_intelligence import CalendarIntelligence


def test_calendar_event_matches_case_by_identifier():
    result = CalendarIntelligence().match(
        [{"event_id": "ev-1", "subject": "Заседание А40-12345/2026"}],
        [{"case_id": "case-1", "case_number": "А40-12345/2026"}],
    )
    assert result[0].case_id == "case-1"
    assert result[0].confidence >= 0.8


def test_calendar_deadline_candidate_is_non_destructive():
    result = CalendarIntelligence.deadline_candidates({"event_id": "ev-2", "subject": "Срок обжалования"})
    assert result[0]["kind"] == "legal_deadline_candidate"
