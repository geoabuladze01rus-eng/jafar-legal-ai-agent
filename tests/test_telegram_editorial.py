import pytest

from jafar.editorial import EditorialPost, EditorialRisk, requires_human_review
from jafar.integrations.telegram import TelegramBotClient


def test_editorial_posts_require_approval_by_default() -> None:
    post = EditorialPost(title="Test", body="Body")
    assert post.requires_human_approval is True
    assert requires_human_review(post) is True


def test_high_risk_posts_require_approval() -> None:
    post = EditorialPost(
        title="Sensitive",
        body="Body",
        risk=EditorialRisk.HIGH,
        requires_human_approval=False,
    )
    assert requires_human_review(post) is True


def test_poll_validation_is_local() -> None:
    # The client validates the Telegram poll option count before network I/O.
    client = TelegramBotClient("test-token")
    with pytest.raises(ValueError):
        import asyncio

        asyncio.run(client.send_poll("@channel", "Question", ["Only one"]))
