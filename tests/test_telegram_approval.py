from jafar.telegram_approval import TelegramApprovalService, TelegramInbound


def test_telegram_reply_requires_approval():
    action = TelegramApprovalService().classify(
        TelegramInbound("chat-1", "Нужен ответ подписчику", "m-1", "2026-08-21T21:00:00Z")
    )
    assert action.action == "propose_reply"
    assert action.requires_approval is True
    assert TelegramApprovalService().can_publish(action, False) is False
    assert TelegramApprovalService().can_publish(action, True) is True
