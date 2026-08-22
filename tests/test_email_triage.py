from jafar.email_triage import EmailTriage


def test_email_triage_proposes_analysis_for_legal_message():
    result = EmailTriage().classify(
        message_id="m1",
        subject="Претензия по договору",
        preview="Просим подготовить ответ адвоката",
        attachment_count=2,
    )
    assert result.action == "prepare_legal_analysis"
    assert result.legal_relevance > 0
    assert result.attachment_count == 2


def test_email_triage_does_not_perform_external_action():
    result = EmailTriage().classify(message_id="m2", subject="Новости", preview="Обновление сайта")
    assert result.action == "triage"
