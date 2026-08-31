from datetime import datetime, timezone

from jafar.domains import MatterType
from jafar.legal_models import Matter
from jafar.matters import MatterStore
from jafar.persistent_matter_catalog import PersistentMatterCatalog


def test_catalog_resolves_from_repository_state() -> None:
    repository = MatterStore()
    now = datetime.now(timezone.utc)
    repository.create(
        Matter(
            id="matter-pavlik",
            title="Дело Павлика В.А.",
            matter_type=MatterType.CRIMINAL,
            client_name="Павлик В.А.",
            case_number="12604008104000012",
            created_at=now,
            updated_at=now,
        )
    )

    route = PersistentMatterCatalog(repository).route(
        "Проанализируй дело Павлика и найди противоречия"
    )

    assert route.is_research is True
    assert route.matter_id == "matter-pavlik"
