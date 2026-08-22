from jafar.comment_classifier import CommentIntent, classify_comment


def test_classifies_legal_help():
    assert classify_comment("У меня проблема, что делать с жалобой?") == CommentIntent.LEGAL_HELP


def test_classifies_personal_data():
    assert classify_comment("Вот мой номер телефона") == CommentIntent.PERSONAL_DATA


def test_classifies_escalation_topics():
    assert classify_comment("Что делать при пытках в колонии?") == CommentIntent.ESCALATE


def test_classifies_aggression():
    assert classify_comment("Вы идиоты") == CommentIntent.AGGRESSIVE


def test_classifies_question():
    assert classify_comment("Почему суд так решил?") == CommentIntent.QUESTION


def test_classifies_discussion():
    assert classify_comment("Интересное мнение, я думаю иначе") == CommentIntent.DISCUSSION
