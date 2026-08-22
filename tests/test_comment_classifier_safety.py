from jafar.comment_classifier import CommentIntent, classify_comment


def test_ambiguous_investigator_topic_requires_escalation():
    assert classify_comment("Следователь вызвал меня на допрос") is CommentIntent.ESCALATE


def test_prison_topic_requires_escalation():
    assert classify_comment("Что происходит в колонии?") is CommentIntent.ESCALATE


def test_plain_question_remains_question():
    assert classify_comment("Почему изменился закон?") is CommentIntent.QUESTION


def test_personal_data_wins_over_question():
    assert classify_comment("Можно ли указать телефон в комментарии?") is CommentIntent.PERSONAL_DATA
