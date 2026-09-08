from jafar.audit_trail import AuditTrail
from jafar.telegram_delivery import (
    DeliveryLedgerState,
    InMemoryPublicationDeliveryLedger,
    PublicationAudit,
    payload_hash,
)


def test_claim_prevents_duplicate_and_sent_is_terminal() -> None:
    ledger = InMemoryPublicationDeliveryLedger()
    digest = payload_hash({"a": 1})

    assert ledger.claim("p1", payload_hash=digest) is True
    assert ledger.claim("p1", payload_hash=digest) is False

    ledger.mark_sent("p1", telegram_message_id=7)

    record = ledger.get("p1")
    assert record is not None
    assert record.state is DeliveryLedgerState.SENT
    assert ledger.claim("p1", payload_hash=digest) is False


def test_uncertain_blocks_blind_retry_and_can_be_reconciled() -> None:
    ledger = InMemoryPublicationDeliveryLedger()
    digest = payload_hash({"a": 1})
    ledger.claim("p1", payload_hash=digest)
    ledger.mark_uncertain("p1", note="timeout after POST")

    assert ledger.claim("p1", payload_hash=digest) is False

    ledger.reconcile_sent("p1", telegram_message_id=9, note="verified in channel")
    record = ledger.get("p1")
    assert record is not None
    assert record.telegram_message_id == 9
    assert record.state is DeliveryLedgerState.SENT


def test_definite_failure_requires_explicit_retry_release() -> None:
    ledger = InMemoryPublicationDeliveryLedger()
    digest = payload_hash({"a": 1})
    ledger.claim("p1", payload_hash=digest)
    ledger.mark_failed("p1", error_code="HTTP_400")

    assert ledger.claim("p1", payload_hash=digest) is False
    assert ledger.release_failed_for_retry("p1") is True
    assert ledger.claim("p1", payload_hash=digest) is True


def test_audit_redacts_secrets_recursively() -> None:
    trail = AuditTrail()
    audit = PublicationAudit(trail)

    event = audit.record(
        publication_id="p1",
        event_type="TELEGRAM_SEND_ATTEMPT",
        status="attempt",
        metadata={
            "token": "abc",
            "nested": {"Authorization": "Bearer verysecret"},
        },
    )

    assert event.metadata["token"] == "[REDACTED]"
    assert event.metadata["nested"]["Authorization"] == "[REDACTED]"
