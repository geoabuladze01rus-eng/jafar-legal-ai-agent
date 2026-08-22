from jafar.telegram_case_matcher import TelegramCaseMatcher


def test_telegram_case_matcher_uses_case_identifiers():
    result = TelegramCaseMatcher().match(
        message="Нужно обсудить дело А40-12345/2026",
        cases=[
            {"case_id": "1", "case_number": "А40-12345/2026"},
            {"case_id": "2", "case_number": "А40-99999/2026"},
        ],
    )
    assert result[0].case_id == "1"
    assert result[0].score > result[1].score if len(result) > 1 else True


def test_telegram_case_matcher_returns_no_candidates_for_unrelated_message():
    result = TelegramCaseMatcher().match(message="Привет", cases=[])
    assert result == []
