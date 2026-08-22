from jafar.comment_classifier import CommentIntent
from jafar.comment_response_engine import prepare_response


def test_response_engine_combines_classification_and_policy():
    draft = prepare_response("У меня проблема, что делать с жалобой?")
    assert draft.intent is CommentIntent.LEGAL_HELP
    assert draft.decision.mode == "auto_reply"
    assert draft.decision.draft


def test_response_engine_escalates_sensitive_topic():
    draft = prepare_response("Что делать при пытках?")
    assert draft.intent is CommentIntent.ESCALATE
    assert draft.decision.mode == "editor_review"
