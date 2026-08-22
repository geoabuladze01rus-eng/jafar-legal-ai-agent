import pytest

from jafar.supabase_inbound_state import SupabaseInboundStateStore


class FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code

    def raise_for_status(self):
        raise RuntimeError(f"unexpected status {self.status_code}")


class FakeClient:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        return self.response


@pytest.mark.asyncio
async def test_201_claims_update(monkeypatch):
    import jafar.supabase_inbound_state as module
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: FakeClient(FakeResponse(201)))
    assert await SupabaseInboundStateStore("https://example", "key").claim_update(1) is True


@pytest.mark.asyncio
async def test_409_is_duplicate(monkeypatch):
    import jafar.supabase_inbound_state as module
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: FakeClient(FakeResponse(409)))
    assert await SupabaseInboundStateStore("https://example", "key").claim_update(1) is False


@pytest.mark.asyncio
async def test_other_http_errors_are_not_treated_as_duplicates(monkeypatch):
    import jafar.supabase_inbound_state as module
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: FakeClient(FakeResponse(500)))
    with pytest.raises(RuntimeError):
        await SupabaseInboundStateStore("https://example", "key").claim_update(1)
