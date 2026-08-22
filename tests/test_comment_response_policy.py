from jafar.comment_classifier import CommentIntent
from jafar.comment_response_policy import build_response


def test_personal_data_is_moderated():
    result = build_response(CommentIntent.PERSONAL_DATA, "мой телефон 123")
    assert result.mode == "moderate"
    assert "персональные данные" in result.draft


def test_sensitive_topics_require_editor_review():
    result = build_response(CommentIntent.ESCALATE, "пытки")
    assert result.mode == "editor_review"


def test_legal_help_gets_general_information_disclaimer():
    result = build_response(CommentIntent.LEGAL_HELP, "что делать")
    assert result.mode == "auto_reply"
    assert "индивидуальную юридическую помощь" in result.draft


def test_aggression_gets_neutral_reply():
    result = build_response(CommentIntent.AGGRESSIVE, "вы идиоты")
    assert result.mode == "auto_reply"
    assert "факты" in result.draft
