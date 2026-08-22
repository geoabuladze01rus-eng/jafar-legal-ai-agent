from jafar.email_case_matcher import EmailCaseMatcher


def test_email_case_matcher_ranks_exact_identifiers_first():
    cases = [
        {"case_id": "case-1", "case_number": "А40-12345/2026", "keywords": ["поставка"]},
        {"case_id": "case-2", "case_number": "А40-99999/2026", "keywords": ["поставка"]},
    ]
    result = EmailCaseMatcher().match(
        subject="Документы по делу А40-12345/2026",
        body="Просим изучить договор поставки.",
        cases=cases,
    )
    assert result[0].case_id == "case-1"
    assert result[0].score > result[1].score


def test_email_case_matcher_does_not_attach_without_match():
    result = EmailCaseMatcher().match(subject="Новости", body="Без номера дела", cases=[])
    assert result == []
