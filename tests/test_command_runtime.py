from datetime import UTC, datetime

from jafar.command_runtime import JafarCommandRuntime
from jafar.domains import MatterType
from jafar.legal_models import Matter
from jafar.matters import MatterStore


def make_store() -> MatterStore:
    store = MatterStore()
    now = datetime.now(UTC)
    store.create(
        Matter(
            id="matter-1",
            title="Павлик",
            matter_type=MatterType.CRIMINAL,
            client_name="Павлик Вадим Александрович",
            opposing_party=None,
            court_or_authority="СУ СК России",
            case_number="12604008104000012",
            created_at=now,
            updated_at=now,
        )
    )
    return store


def test_read_only_commands_do_not_require_approval():
    runtime = JafarCommandRuntime(make_store())

    health = runtime.execute("health", request_id="req-health")
    matters = runtime.execute("list_matters", request_id="req-matters")

    assert health.approval_required is False
    assert health.message == "Юстиция на связи."
    assert matters.approval_required is False
    assert matters.data["count"] == 1
    assert matters.data["matters"][0]["id"] == "matter-1"


def test_unknown_intent_is_not_executed():
    runtime = JafarCommandRuntime(make_store())

    result = runtime.execute("send_email", request_id="req-send")

    assert result.approval_required is False
    assert result.data is None
    assert "не найден" in result.message.lower()
