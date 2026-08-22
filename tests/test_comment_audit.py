from jafar.comment_audit import make_audit_record
from jafar.comment_classifier import CommentIntent
from jafar.comment_response_engine import prepare_response
from jafar.telegram_inbound import TelegramComment


def test_audit_record_preserves_normal_metadata():
    comment = TelegramComment(1, "-100", 2, "55", "reader", "Почему суд так решил?")
    record = make_audit_record(comment, prepare_response(comment.text))
    assert record.user_id == "55"
    assert record.username == "reader"
    assert record.intent == CommentIntent.QUESTION.value
    assert record.status == "draft"
    assert record.created_at


def test_personal_data_does_not_copy_user_identity_into_audit():
    comment = TelegramComment(1, "-100", 2, "55", "reader", "мой телефон 123456")
    record = make_audit_record(comment, prepare_response(comment.text))
    assert record.intent == CommentIntent.PERSONAL_DATA.value
    assert record.user_id is None
    assert record.username is None
