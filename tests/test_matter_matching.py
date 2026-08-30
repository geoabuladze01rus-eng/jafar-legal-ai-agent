from datetime import UTC, datetime

from jafar.legal_models import Matter
from jafar.matter_matching import MatterMatcher


def matter(
    matter_id: str,
    title: str,
    case_number: str | None = None,
    client_name: str | None = None,
    opposing_party: str | None = None,
) -> Matter:
    now = datetime.now(UTC)
    return Matter(
        id=matter_id,
        title=title,
        matter_type="general",
        case_number=case_number,
        client_name=client_name,
        opposing_party=opposing_party,
        created_at=now,
        updated_at=now,
    )


def test_exact_case_number_is_auto_linked() -> None:
    matcher = MatterMatcher()
    result = matcher.best_match(
        "Документ по делу А40-12345/26",
        [matter("m1", "Спор о взыскании", "А40-12345/26")],
    )
    assert result is not None
    assert result.matter_id == "m1"
    assert result.score >= 0.75


def test_weak_title_match_does_not_mutate_matter() -> None:
    matcher = MatterMatcher()
    result = matcher.best_match(
        "Вопрос по взысканию",
        [matter("m1", "Спор о взыскании")],
    )
    assert result is None


def test_equal_strong_candidates_are_treated_as_ambiguous() -> None:
    matcher = MatterMatcher(min_margin=0.10)
    result = matcher.best_match(
        "А40-12345/26 спор с ООО Альфа",
        [
            matter("m1", "Спор с ООО Альфа", "А40-12345/26"),
            matter("m2", "Спор с ООО Альфа", "А40-12345/26"),
        ],
    )
    assert result is None


def test_candidate_explanations_are_preserved() -> None:
    matcher = MatterMatcher()
    candidates = matcher.candidates(
        "А40-12345/26 ООО Альфа",
        [matter("m1", "Спор с ООО Альфа", "А40-12345/26")],
    )
    assert candidates
    assert "совпадает номер дела" in candidates[0].reasons
