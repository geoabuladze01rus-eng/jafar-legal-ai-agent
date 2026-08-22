from jafar.telegram_inbound import normalize_update


def test_normalize_group_comment():
    result = normalize_update({
        "update_id": 42,
        "message": {
            "message_id": 7,
            "text": "  Что делать?  ",
            "chat": {"id": -100123, "type": "supergroup"},
            "from": {"id": 55, "username": "reader"},
        },
    })
    assert result is not None
    assert result.update_id == 42
    assert result.chat_id == "-100123"
    assert result.message_id == 7
    assert result.user_id == "55"
    assert result.username == "reader"
    assert result.text == "Что делать?"


def test_ignore_private_messages_and_non_text_updates():
    assert normalize_update({"message": {"chat": {"id": 1, "type": "private"}, "text": "hi"}}) is None
    assert normalize_update({"message": {"chat": {"id": -1, "type": "group"}}}) is None
