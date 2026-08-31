from jafar.comment_pipeline import process_update


def _update(text: str) -> dict:
    return {
        "update_id": 100,
        "message": {
            "message_id": 7,
            "chat": {"id": 12345, "type": "supergroup"},
            "from": {"id": 77, "username": "reader"},
            "text": text,
        },
    }


def test_safe_comment_is_marked_for_auto_reply() -> None:
    result = process_update(_update("Почему вы пишете об этом?"))

    assert result is not None
    assert result.safety.allowed is True
    assert result.safety.reason == "safe_auto_reply"
    assert result.audit.status == "approved_for_auto_reply"


def test_sensitive_comment_is_blocked_before_outbound() -> None:
    result = process_update(_update("У меня паспорт и телефон опубликованы здесь"))

    assert result is not None
    assert result.safety.allowed is False
    assert result.safety.reason == "requires_moderation_or_editor_review"
    assert result.audit.status == "blocked_for_review"


def test_escalation_topic_is_blocked_before_outbound() -> None:
    result = process_update(_update("Меня задержали, что делать?"))

    assert result is not None
    assert result.safety.allowed is False
    assert result.safety.reason == "requires_moderation_or_editor_review"
    assert result.audit.status == "blocked_for_review"
