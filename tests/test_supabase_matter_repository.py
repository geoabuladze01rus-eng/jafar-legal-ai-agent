from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any

from jafar.domains import MatterType
from jafar.legal_models import Deadline, Matter
from jafar.supabase_matter_repository import SupabaseMatterRepository


class FakeQuery:
    def __init__(self, client: "FakeSupabase", table: str) -> None:
        self.client = client
        self.table_name = table
        self.filters: list[tuple[str, Any]] = []
        self.single = False
        self.insert_payload: Any = None

    def select(self, _: str) -> "FakeQuery":
        return self

    def eq(self, field: str, value: Any) -> "FakeQuery":
        self.filters.append((field, value))
        return self

    def maybe_single(self) -> "FakeQuery":
        self.single = True
        return self

    def order(self, _: str) -> "FakeQuery":
        return self

    def insert(self, payload: Any) -> "FakeQuery":
        self.insert_payload = deepcopy(payload)
        return self

    def execute(self) -> SimpleNamespace:
        if self.insert_payload is not None:
            rows = (
                self.insert_payload
                if isinstance(self.insert_payload, list)
                else [self.insert_payload]
            )
            self.client.data.setdefault(self.table_name, []).extend(deepcopy(rows))
            return SimpleNamespace(data=deepcopy(rows))

        rows = deepcopy(self.client.data.get(self.table_name, []))
        for field, value in self.filters:
            rows = [row for row in rows if row.get(field) == value]
        if self.single:
            return SimpleNamespace(data=rows[0] if rows else None)
        return SimpleNamespace(data=rows)


class FakeSupabase:
    def __init__(self, data: dict[str, list[dict[str, Any]]]) -> None:
        self.data = deepcopy(data)

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self, name)

    def rpc(self, function: str, params: dict[str, Any]) -> Any:
        raise AssertionError(f"Unexpected RPC: {function} {params}")


def matter_row(matter_id: str = "matter-1", *, status: str = "active") -> dict[str, Any]:
    return {
        "id": matter_id,
        "owner_user_id": "owner-1",
        "title": "Павлик",
        "matter_type": "criminal",
        "client_name": "Павлик В.А.",
        "opposing_party": None,
        "court_or_authority": "СУ СК России",
        "case_number": "12604008104000012",
        "status": status,
        "created_at": "2026-08-20T10:00:00+00:00",
        "updated_at": "2026-08-28T10:00:00+00:00",
    }


def deadline_row(
    title: str,
    due_date: str,
    *,
    confidence: float = 0.8,
) -> dict[str, Any]:
    return {
        "matter_id": "matter-1",
        "owner_user_id": "owner-1",
        "title": title,
        "due_date": due_date,
        "source_text": "Источник срока",
        "confidence": confidence,
    }


def test_get_hydrates_deadlines_from_persistent_table() -> None:
    client = FakeSupabase(
        {
            "matters": [matter_row()],
            "deadlines": [deadline_row("Заседание", "2026-09-01T00:00:00+00:00")],
        }
    )
    repo = SupabaseMatterRepository(client, "owner-1")

    matter = repo.get("matter-1")

    assert matter is not None
    assert matter.status == "active"
    assert len(matter.deadlines) == 1
    assert matter.deadlines[0].title == "Заседание"
    assert matter.deadlines[0].due_date == date(2026, 9, 1)
    assert matter.deadlines[0].confidence == 0.8


def test_list_matters_groups_only_owner_deadlines_by_matter() -> None:
    second = matter_row("matter-2", status="closed")
    second["title"] = "Завершённое дело"
    client = FakeSupabase(
        {
            "matters": [matter_row(), second],
            "deadlines": [
                deadline_row("Первый срок", "2026-09-01"),
                {
                    "matter_id": "matter-2",
                    "owner_user_id": "owner-1",
                    "title": "Архивный срок",
                    "due_date": "2026-09-02",
                    "source_text": None,
                    "confidence": 0.5,
                },
                {
                    "matter_id": "matter-1",
                    "owner_user_id": "other-owner",
                    "title": "Чужой срок",
                    "due_date": "2026-09-03",
                    "source_text": None,
                    "confidence": 1.0,
                },
            ],
        }
    )
    repo = SupabaseMatterRepository(client, "owner-1")

    matters = repo.list_matters()

    by_id = {item.id: item for item in matters}
    assert [item.title for item in by_id["matter-1"].deadlines] == ["Первый срок"]
    assert [item.title for item in by_id["matter-2"].deadlines] == ["Архивный срок"]
    assert by_id["matter-2"].status == "closed"


def test_add_deadlines_matches_in_memory_deduplication_semantics() -> None:
    existing = deadline_row("Обжалование", "2026-09-01", confidence=0.7)
    client = FakeSupabase({"matters": [matter_row()], "deadlines": [existing]})
    repo = SupabaseMatterRepository(client, "owner-1")

    repo.add_deadlines(
        "matter-1",
        [
            Deadline(
                title="Обжалование",
                due_date=date(2026, 9, 1),
                source_text="Источник срока",
                confidence=0.7,
            ),
            Deadline(
                title="Ответ прокурора",
                due_date=date(2026, 9, 5),
                source_text="Новый источник",
                confidence=0.9,
            ),
        ],
    )

    stored = [row for row in client.data["deadlines"] if row["owner_user_id"] == "owner-1"]
    assert len(stored) == 2
    assert stored[-1]["title"] == "Ответ прокурора"
    assert stored[-1]["confidence"] == 0.9


def test_create_persists_status_and_initial_deadlines() -> None:
    client = FakeSupabase({"matters": [], "deadlines": []})
    repo = SupabaseMatterRepository(client, "owner-1")
    now = datetime(2026, 8, 28, 12, tzinfo=timezone.utc)
    matter = Matter(
        id="new-matter",
        title="Новое дело",
        matter_type=MatterType.CRIMINAL,
        status="active",
        deadlines=[
            Deadline(
                title="Срок",
                due_date=date(2026, 9, 10),
                confidence=0.75,
            )
        ],
        created_at=now,
        updated_at=now,
    )

    repo.create(matter)

    assert client.data["matters"][0]["status"] == "active"
    assert client.data["matters"][0]["owner_user_id"] == "owner-1"
    assert client.data["deadlines"][0]["matter_id"] == "new-matter"
    assert client.data["deadlines"][0]["confidence"] == 0.75
