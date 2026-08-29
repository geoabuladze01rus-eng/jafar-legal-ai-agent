from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

from jafar.domains import MatterType
from jafar.legal_models import Deadline, Matter
from jafar.supabase_matter_repository import SupabaseMatterRepository


class RecordingRPC:
    def __init__(self, response: Any = None) -> None:
        self.response = response

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self.response)


class AtomicCreateClient:
    def __init__(self) -> None:
        self.rpc_calls: list[tuple[str, dict[str, Any]]] = []
        self.table_calls: list[str] = []

    def rpc(self, function: str, params: dict[str, Any]) -> RecordingRPC:
        self.rpc_calls.append((function, params))
        return RecordingRPC()

    def table(self, name: str) -> Any:
        self.table_calls.append(name)
        raise AssertionError("server-mode create must not perform split table inserts")


def test_server_mode_create_uses_single_atomic_rpc() -> None:
    client = AtomicCreateClient()
    repo = SupabaseMatterRepository(client, "owner-1", server_mode=True)
    now = datetime(2026, 8, 28, 12, tzinfo=UTC)
    matter = Matter(
        id="00000000-0000-0000-0000-000000000001",
        title="Павлик",
        matter_type=MatterType.CRIMINAL,
        client_name="Павлик В.А.",
        case_number="12604008104000012",
        deadlines=[
            Deadline(
                title="Срок обжалования",
                due_date=date(2026, 9, 4),
                source_text="Судебный акт",
                confidence=0.9,
            )
        ],
        created_at=now,
        updated_at=now,
    )

    created = repo.create(matter)

    assert created is matter
    assert client.table_calls == []
    assert len(client.rpc_calls) == 1
    function, params = client.rpc_calls[0]
    assert function == "create_matter_for_owner"
    assert params["p_owner_user_id"] == "owner-1"
    assert params["p_matter_id"] == matter.id
    assert params["p_status"] == "active"
    assert params["p_deadlines"] == [
        {
            "title": "Срок обжалования",
            "due_date": "2026-09-04",
            "source_text": "Судебный акт",
            "confidence": 0.9,
        }
    ]


def test_atomic_create_migration_is_service_role_only_and_transactional() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    sql = (
        root
        / "supabase"
        / "migrations"
        / "20260828165000_add_atomic_matter_create_rpc.sql"
    ).read_text(encoding="utf-8").casefold()

    assert "create or replace function public.create_matter_for_owner" in sql
    assert "insert into public.matters" in sql
    assert "insert into public.deadlines" in sql
    assert "from authenticated" in sql
    assert "to service_role" in sql
    assert "deadline_confidence_out_of_range" in sql
