from jafar.editorial_policy import RiskLevel, decide


def test_routine_comment_can_be_automatic() -> None:
    assert decide("Какая тема будет завтра?").level == RiskLevel.AUTO


def test_legal_comment_requires_review() -> None:
    assert decide("Что делать, если меня вызывают на допрос?").level == RiskLevel.REVIEW


def test_sensitive_data_requires_owner() -> None:
    assert decide("Вот мой паспорт и адрес проживания").level == RiskLevel.OWNER
