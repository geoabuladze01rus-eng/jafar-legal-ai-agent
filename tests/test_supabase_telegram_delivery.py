from __future__ import annotations

from datetime import datetime, timezone

from jafar.supabase_telegram_delivery import SupabaseTelegramDeliveryLedger
from jafar.telegram_delivery import DeliveryLedgerState


class RpcResult:
    def __init__(self, data=None):
        self.data = data


class RpcCall:
    def __init__(self, data=None):
        self.data = data

    def execute(self):
        return RpcResult(self.data)


class FakeClient:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.responses: dict[str, object] = {}

    def rpc(self, name, params):
        self.calls.append((name, params))
        return RpcCall(self.responses.get(name))


def test_claim_uses_atomic_rpc_and_returns_boolean() -> None:
    client = FakeClient()
    client.responses["claim_telegram_publication"] = True
    ledger = SupabaseTelegramDeliveryLedger(client)

    assert ledger.claim("tg_1", payload_hash="a" * 64) is True
    assert client.calls == [
        (
            "claim_telegram_publication",
            {"p_publication_id": "tg_1", "p_payload_hash": "a" * 64},
        )
    ]


def test_failed_release_and_reconciliation_use_explicit_rpcs() -> None:
    client = FakeClient()
    client.responses["release_telegram_publication_failed"] = True
    ledger = SupabaseTelegramDeliveryLedger(client)

    ledger.mark_failed("tg_1", error_code="telegram_500")
    assert ledger.release_failed_for_retry("tg_1") is True
    ledger.mark_uncertain("tg_2", note="response lost")
    ledger.reconcile_sent("tg_2", telegram_message_id=42, note="verified in channel")

    names = [name for name, _ in client.calls]
    assert names == [
        "mark_telegram_publication_failed",
        "release_telegram_publication_failed",
        "mark_telegram_publication_uncertain",
        "reconcile_telegram_publication_sent",
    ]


def test_get_parses_persistent_delivery_record() -> None:
    now = datetime.now(timezone.utc).isoformat()
    client = FakeClient()
    client.responses["get_telegram_publication_delivery"] = {
        "publication_id": "tg_1",
        "payload_hash": "b" * 64,
        "state": "uncertain",
        "claimed_at": now,
        "updated_at": now,
        "telegram_message_id": None,
        "error_code": None,
        "reconciliation_note": "manual check required",
    }
    ledger = SupabaseTelegramDeliveryLedger(client)

    record = ledger.get("tg_1")

    assert record is not None
    assert record.publication_id == "tg_1"
    assert record.state is DeliveryLedgerState.UNCERTAIN
    assert record.payload_hash == "b" * 64
    assert record.reconciliation_note == "manual check required"
    assert record.claimed_at.tzinfo is not None


def test_get_returns_none_for_missing_record() -> None:
    client = FakeClient()
    client.responses["get_telegram_publication_delivery"] = None
    ledger = SupabaseTelegramDeliveryLedger(client)

    assert ledger.get("missing") is None
