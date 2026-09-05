from datetime import datetime, timezone

from jafar.memory_command_router import NaturalLanguageMemoryRouter
from jafar.memory_commands import MemoryCommandExecutor
from jafar.memory_models import MemoryKind, MemoryRecord, MemorySearchResult


class FakeMemoryService:
    def __init__(self) -> None:
        self.saved = []
        self.deleted = []

    def remember(self, *, content, kind, matter_id=None, source=None, confidence=1.0):
        self.saved.append((content, kind, matter_id, source))
        return MemoryRecord(
            id="mem-1",
            owner_user_id="owner-1",
            kind=kind,
            content=content,
            matter_id=matter_id,
            source=source,
            confidence=confidence,
            created_at=datetime.now(timezone.utc),
        )

    def recall(self, query, *, matter_id=None, limit=8, min_similarity=0.0):
        memory = MemoryRecord(
            id="mem-2",
            owner_user_id="owner-1",
            kind=MemoryKind.DECISION,
            content="Решили сначала получить обвинительное заключение.",
            matter_id=matter_id,
            created_at=datetime.now(timezone.utc),
        )
        return [MemorySearchResult(memory=memory, similarity=0.91)]

    def forget(self, memory_id):
        self.deleted.append(memory_id)
        return True


def test_router_only_recognizes_explicit_remember_command():
    router = NaturalLanguageMemoryRouter()
    assert router.route("Мне нравится графитовый цвет").intent is None
    route = router.route("Джафар, запомни я предпочитаю краткие отчеты")
    assert route.intent == "remember"
    assert route.kind == MemoryKind.PREFERENCE
    assert route.content == "я предпочитаю краткие отчеты"


def test_remember_requires_approval_before_persistent_write():
    service = FakeMemoryService()
    executor = MemoryCommandExecutor(service)
    route = NaturalLanguageMemoryRouter().route("Запомни решили сначала проверить материалы дела")

    pending = executor.execute(route, approved=False, matter_id="matter-1")
    assert pending.approval_required is True
    assert service.saved == []

    completed = executor.execute(route, approved=True, matter_id="matter-1")
    assert completed.approval_required is False
    assert completed.data["memory_id"] == "mem-1"
    assert service.saved[0][2] == "matter-1"


def test_recall_is_read_only_and_needs_no_approval():
    service = FakeMemoryService()
    executor = MemoryCommandExecutor(service)
    route = NaturalLanguageMemoryRouter().route("Что мы решили по этому делу?")
    result = executor.execute(route, approved=False, matter_id="matter-1")
    assert result.approval_required is False
    assert result.data["memories"][0]["id"] == "mem-2"


def test_forget_requires_explicit_id_and_approval():
    service = FakeMemoryService()
    executor = MemoryCommandExecutor(service)
    route = NaturalLanguageMemoryRouter().route("Забудь память mem-2")
    pending = executor.execute(route, approved=False)
    assert pending.approval_required is True
    assert service.deleted == []
    executor.execute(route, approved=True)
    assert service.deleted == ["mem-2"]
