from jafar.comment_pipeline import process_update


def test_pipeline_processes_comment_end_to_end():
    result = process_update({
        "update_id": 100,
        "message": {
            "message_id": 12,
            "text": "Почему суд так решил?",
            "chat": {"id": -100123, "type": "supergroup"},
            "from": {"id": 55, "username": "reader"},
        },
    })
    assert result is not None
    assert result.comment.message_id == 12
    assert result.draft.decision.draft
    assert result.audit.intent == "question"
    assert result.audit.status == "draft"


def test_pipeline_ignores_non_comment_updates():
    assert process_update({"update_id": 101, "message": {"chat": {"id": 1, "type": "private"}, "text": "hello"}}) is None
