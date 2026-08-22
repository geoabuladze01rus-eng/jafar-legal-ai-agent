from jafar.email_intelligence import EmailIntelligence


def test_legal_email_is_marked_for_analysis():
    result = EmailIntelligence().assess({"subject": "Арбитражное дело", "bodyPreview": "Нужно подготовить иск"})
    assert result.relevant is True
    assert result.suggested_action == "prepare_legal_analysis"


def test_non_legal_email_is_not_marked_for_legal_analysis():
    result = EmailIntelligence().assess({"subject": "Акция магазина", "bodyPreview": "Скидка 30%"})
    assert result.relevant is False
