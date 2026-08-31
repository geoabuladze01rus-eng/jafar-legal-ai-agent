from types import SimpleNamespace

import pytest

from jafar.supabase_memory_repository import SupabaseMemoryRepository


class RpcCall:
    def __init__(self, rows):
        self.rows = rows

    def execute(self):
        return SimpleNamespace(data=self.rows)


class FakeClient:
    def __init__(self, rows):
        self.rows = rows
        self.function = None
        self.params = None

    def rpc(self, function, params):
        self.function = function
        self.params = params
        return RpcCall(self.rows)


def _row(*, owner="owner-1", matter="matter-1"):
    return {
        "id": "memory-1",
        "owner_user_id": owner,
        "matter_id": matter,
        "kind": "decision",
        "content": "Решение по делу",
        "source": "user",
        "confidence": 1.0,
        "created_at": "2026-08-31T00:00:00+00:00",
        "similarity": 0.88,
    }


def test_search_sends_fixed_owner_and_matter_to_rpc() -> None:
    client = FakeClient([_row()])
    repo = SupabaseMemoryRepository(client=client, owner_user_id="owner-1")

    results = repo.search(embedding=tuple([0.1] * 1536), matter_id="matter-1", limit=5)

    assert results[0].similarity == 0.88
    assert client.function == "match_assistant_memories"
    assert client.params["p_owner_user_id"] == "owner-1"
    assert client.params["p_matter_id"] == "matter-1"
    assert client.params["p_match_count"] == 5


def test_search_rejects_cross_owner_result() -> None:
    repo = SupabaseMemoryRepository(client=FakeClient([_row(owner="owner-2")]), owner_user_id="owner-1")
    with pytest.raises(RuntimeError, match="different owner"):
        repo.search(embedding=tuple([0.1] * 1536))


def test_search_rejects_other_matter_but_allows_global_memory() -> None:
    repo = SupabaseMemoryRepository(client=FakeClient([_row(matter="matter-2")]), owner_user_id="owner-1")
    with pytest.raises(RuntimeError, match="different matter"):
        repo.search(embedding=tuple([0.1] * 1536), matter_id="matter-1")

    global_repo = SupabaseMemoryRepository(client=FakeClient([_row(matter=None)]), owner_user_id="owner-1")
    assert global_repo.search(embedding=tuple([0.1] * 1536), matter_id="matter-1")


def test_embedding_dimension_is_validated() -> None:
    repo = SupabaseMemoryRepository(client=FakeClient([]), owner_user_id="owner-1")
    with pytest.raises(ValueError, match="1536"):
        repo.search(embedding=(0.1, 0.2))
