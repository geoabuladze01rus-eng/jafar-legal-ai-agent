from __future__ import annotations

from jafar.document_status import DocumentStatus
from jafar.supabase_document_retry import SupabaseRetryStatusStore


class RpcResult:
    def __init__(self, data=None):
        self.data = data


class FakeQuery:
    def __init__(self, client):
        self.client = client

    def select(self, *_): return self
    def eq(self, *_): return self
    def single(self): return self
    def execute(self): return RpcResult({"processing_status": self.client.status})


class FakeClient:
    def __init__(self, status):
        self.status = status
        self.claims = 0

    def table(self, *_): return FakeQuery(self)

    def rpc(self, name, args):
        if name == "claim_failed_document_for_retry":
            self.claims += 1
            if self.status != "failed":
                raise AssertionError("second claimant must not acquire document")
            self.status = "processing"
        return RpcCall()


class RpcCall:
    def execute(self): return RpcResult()


def test_second_retry_claim_cannot_acquire_processing_document():
    client = FakeClient("failed")
    store = SupabaseRetryStatusStore(client)

    assert store.get_status(storage_path="m/contract.pdf") is DocumentStatus.FAILED
    store.set_status(storage_path="m/contract.pdf", status=DocumentStatus.PROCESSING)
    assert client.status == "processing"

    try:
        store.set_status(storage_path="m/contract.pdf", status=DocumentStatus.PROCESSING)
    except AssertionError:
        pass
    else:
        raise AssertionError("second retry claim unexpectedly succeeded")

    assert client.claims == 2
