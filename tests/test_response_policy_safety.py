from jafar.comment_classifier import CommentIntent
from jafar.comment_response_policy import build_response


def test_personal_data_is_moderated():
    decision = build_response(CommentIntent.PERSONAL_DATA, "мой телефон 123")
    assert decision.mode == "moderate"
    assert "персональные данные" in decision.draft.lower()


def test_escalated_topic_requires_editor_review():
    decision = build_response(CommentIntent.ESCALATE, "сообщение о пытках")
    assert decision.mode == "editor_review"


def test_ordinary_question_can_use_auto_reply():
    decision = build_response(CommentIntent.QUESTION, "что изменилось в законе?")
    assert decision.mode == "auto_reply"


def test_legal_help_is_not_individual_legal_advice():
    decision = build_response(CommentIntent.LEGAL_HELP, "что делать лично мне?")
    assert decision.mode == "auto_reply"
    assert "индивидуальную юридическую помощь" in decision.draft
