class TelegramDeliveryUncertainError(RuntimeError):
    """Telegram may have accepted a side effect but confirmation was not received.

    Callers must fail closed and require explicit reconciliation. Never auto-retry.
    """
