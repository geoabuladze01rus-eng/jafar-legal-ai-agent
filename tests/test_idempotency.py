from __future__ import annotations

from jafar.idempotency import InMemoryProcessingLedger


def test_same_message_can_be_claimed_only_once_until_completed():
    ledger = InMemoryProcessingLedger()
    kwargs = {"sender": "client@example.com", "subject": "Case", "received_at": "2026-08-23T07:00:00+00:00"}
    assert ledger.claim("msg-1", **kwargs) is True
    assert ledger.claim("msg-1", **kwargs) is False
    ledger.mark_processed("msg-1")
    assert ledger.claim("msg-1", **kwargs) is False


def test_failed_message_can_be_retried():
    ledger = InMemoryProcessingLedger()
    kwargs = {"sender": "client@example.com", "subject": "Case", "received_at": "2026-08-23T07:00:00+00:00"}
    assert ledger.claim("msg-2", **kwargs) is True
    ledger.mark_failed("msg-2")
    assert ledger.claim("msg-2", **kwargs) is True


def test_different_messages_can_be_claimed_independently():
    ledger = InMemoryProcessingLedger()
    kwargs = {"sender": "client@example.com", "subject": "Case", "received_at": "2026-08-23T07:00:00+00:00"}
    assert ledger.claim("msg-a", **kwargs) is True
    assert ledger.claim("msg-b", **kwargs) is True
