from datetime import datetime, timezone

from jafar.domains import MatterType
from jafar.legal_models import Matter
from jafar.matter_matching import MatterMatcher


def matter(**kwargs):
    now = datetime.now(timezone.utc)
    return Matter(
        id=kwargs.get("id", "matter-1"),
        title=kwargs.get("title", "Дело о взыскании задолженности"),
        matter_type=MatterType.CIVIL,
        client_name=kwargs.get("client_name", "ООО Альфа"),
        opposing_party=kwargs.get("opposing_party", "ООО Бета"),
        court_or_authority=kwargs.get("court_or_authority", "Арбитражный суд Москвы"),
        case_number=kwargs.get("case_number", "А40-12345/2026"),
        created_at=now,
        updated_at=now,
    )


def test_exact_case_number_is_strong_match():
    result = MatterMatcher().best_match("По делу А40-12345/2026 направляется отзыв.", [matter()])
    assert result is not None
    assert result.matter_id == "matter-1"
    assert result.score >= 0.85
    assert "exact case number" in result.reasons


def test_names_can_support_match():
    result = MatterMatcher(minimum_score=0.3).best_match(
        "Документ подготовлен для ООО Альфа против ООО Бета.", [matter()]
    )
    assert result is not None
    assert result.score >= 0.3


def test_ambiguous_document_is_left_unresolved():
    first = matter()
    second = matter(id="matter-2", title="Иное дело", client_name="ООО Гамма", opposing_party="ООО Дельта")
    assert MatterMatcher().best_match("Общий документ без номера дела.", [first, second]) is None
