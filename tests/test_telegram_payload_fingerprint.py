from jafar.telegram_payload_fingerprint import telegram_delivery_fingerprint


def test_fingerprint_matches_make_contract() -> None:
    digest = telegram_delivery_fingerprint(
        chat_id="@iznanka_ugolovki",
        publication_type="quiz",
        content="Текст",
        question="Вопрос?",
        options_json='[{"text":"A"},{"text":"B"}]',
        correct_option_ids_json="[1]",
        explanation="Почему",
    )

    assert digest == "aa4581020e4210bad8bb5a559edee6fb8a5ccda884079a06841aeff34259ba78"


def test_any_delivery_field_change_changes_fingerprint() -> None:
    base = telegram_delivery_fingerprint(
        chat_id="@iznanka_ugolovki",
        publication_type="text",
        content="Исходный текст",
    )
    changed_text = telegram_delivery_fingerprint(
        chat_id="@iznanka_ugolovki",
        publication_type="text",
        content="Измененный текст",
    )
    changed_chat = telegram_delivery_fingerprint(
        chat_id="@another_channel",
        publication_type="text",
        content="Исходный текст",
    )

    assert len(base) == 64
    assert base != changed_text
    assert base != changed_chat
