from datetime import datetime, timezone

from jafar.memory_models import MemoryKind, MemoryRecord, MemorySearchResult
from jafar.memory_service import LongTermMemoryService


class FakeEmbeddings:
    def embed(self, text: str) -> tuple[float, ...]:
        assert text.strip()
        return tuple([0.25] * 1536)


class FakeRepository:
    def __init__(self) -> None:
        self.records: dict[str, MemoryRecord] = {}
        self.last_matter_id = None

    def add(self, **kwargs):
        record = MemoryRecord(
            id="memory-1",
            owner_user_id="owner-1",
            kind=kwargs["kind"],
            content=kwargs["content"],
            matter_id=kwargs.get("matter_id"),
            source=kwargs.get("source"),
            confidence=kwargs.get("confidence", 1.0),
            created_at=datetime.now(timezone.utc),
        )
        self.records[record.id] = record
        return record

    def search(self, **kwargs):
        self.last_matter_id = kwargs.get("matter_id")
        return [MemorySearchResult(memory=next(iter(self.records.values())), similarity=0.91)]

    def list(self, **kwargs):
        self.last_matter_id = kwargs.get("matter_id")
        return list(self.records.values())

    def delete(self, memory_id: str):
        return self.records.pop(memory_id, None) is not None


def test_remember_and_recall_matter_memory() -> None:
    repo = FakeRepository()
    service = LongTermMemoryService(repository=repo, embeddings=FakeEmbeddings())

    saved = service.remember(
        content="По делу принято решение сначала получить текст апелляционного определения.",
        kind=MemoryKind.DECISION,
        matter_id="matter-1",
        source="user",
    )

    assert saved.kind is MemoryKind.DECISION
    results = service.recall("какое решение приняли", matter_id="matter-1")
    assert results[0].memory.id == saved.id
    assert results[0].similarity == 0.91
    assert repo.last_matter_id == "matter-1"


def test_forget_is_explicit() -> None:
    repo = FakeRepository()
    service = LongTermMemoryService(repository=repo, embeddings=FakeEmbeddings())
    saved = service.remember(content="Использовать краткий формат", kind=MemoryKind.PREFERENCE)

    assert service.forget(saved.id) is True
    assert service.forget(saved.id) is False


def test_empty_memory_is_rejected_before_embedding() -> None:
    service = LongTermMemoryService(repository=FakeRepository(), embeddings=FakeEmbeddings())
    try:
        service.remember(content="   ")
    except ValueError as exc:
        assert "content" in str(exc)
    else:
        raise AssertionError("expected ValueError")
