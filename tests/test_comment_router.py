from jafar.comment_router import route_comment
from jafar.editorial_policy import RiskLevel


def test_simple_comment_is_auto_reply():
    route = route_comment("Спасибо за пост!")
    assert route.level == RiskLevel.AUTO
    assert route.action == "auto_reply"


def test_legal_comment_is_queued():
    route = route_comment("Что делать после обыска?")
    assert route.level == RiskLevel.REVIEW
    assert route.action == "queue_for_review"


def test_sensitive_comment_notifies_owner():
    route = route_comment("Мой телефон и адрес проживания: ...")
    assert route.level == RiskLevel.OWNER
    assert route.action == "notify_owner"
