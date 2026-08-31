from datetime import datetime, timezone

from jafar.domains import MatterType
from jafar.legal_models import Matter
from jafar.natural_language_research import NaturalLanguageResearchRouter


def matter(matter_id: str, title: str, client_name: str, case_number: str) -> Matter:
    now = datetime.now(timezone.utc)
    return Matter(
        id=matter_id,
        title=title,
        matter_type=MatterType.CRIMINAL,
        client_name=client_name,
        case_number=case_number,
        created_at=now,
        updated_at=now,
    )


def test_routes_research_by_client_name() -> None:
    router = NaturalLanguageResearchRouter()
    matters = [matter("p1", "Дело Павлика", "Павлик В.А.", "12604008104000012")]
    route = router.route("Проанализируй дело Павлика и найди противоречия", matters)
    assert route.is_research is True
    assert route.matter_id == "p1"
    assert route.ambiguous is False


def test_routes_research_by_case_number() -> None:
    router = NaturalLanguageResearchRouter()
    matters = [matter("p1", "Дело Павлика", "Павлик В.А.", "12604008104000012")]
    route = router.route("Найди в деле 12604008104000012 противоречия", matters)
    assert route.matter_id == "p1"


def test_requires_matter_when_research_intent_has_no_match() -> None:
    router = NaturalLanguageResearchRouter()
    route = router.route("Проанализируй дело и найди противоречия", [])
    assert route.is_research is True
    assert route.matter_id is None


def test_does_not_route_unrelated_command() -> None:
    router = NaturalLanguageResearchRouter()
    route = router.route("Покажи мои дела", [])
    assert route.is_research is False
