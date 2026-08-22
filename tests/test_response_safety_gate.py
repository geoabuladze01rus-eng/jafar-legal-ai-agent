from jafar.comment_classifier import CommentIntent
from jafar.comment_response_policy import build_response
from jafar.response_safety_gate import evaluate_response


def test_safe_question_is_allowed():
    intent = CommentIntent.QUESTION
    decision = build_response(intent, "что изменилось?")
    result = evaluate_response(intent, decision)
    assert result.allowed is True
    assert result.reason == "safe_auto_reply"


def test_personal_data_is_blocked():
    intent = CommentIntent.PERSONAL_DATA
    decision = build_response(intent, "мой телефон")
    result = evaluate_response(intent, decision)
    assert result.allowed is False


def test_editor_review_is_never_auto_sent():
    intent = CommentIntent.ESCALATE
    decision = build_response(intent, "сообщение о пытках")
    result = evaluate_response(intent, decision)
    assert result.allowed is False
    assert result.reason == "requires_moderation_or_editor_review"
