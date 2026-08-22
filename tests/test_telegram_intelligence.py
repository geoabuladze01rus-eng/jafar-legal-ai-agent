from jafar.telegram_intelligence import TelegramIntelligence


def test_telegram_legal_message_is_triaged_for_analysis():
    result = TelegramIntelligence().classify(
        message_id="tg-1",
        text="Пришлите документы по уголовному делу и договор.",
    )
    assert result.action == "prepare_case_analysis"
    assert result.relevance > 0.5


def test_telegram_nonlegal_message_is_not_escalated():
    result = TelegramIntelligence().classify(message_id="tg-2", text="Добрый вечер, как дела?")
    assert result.action == "ignore_or_triage"
    assert result.relevance == 0
