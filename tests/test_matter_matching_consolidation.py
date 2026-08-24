from datetime import datetime, timezone

from jafar.domains import MatterType
from jafar.legal_models import Matter
from jafar.matter_matching import MatterMatcher


def matter(matter_id: str, *, case_number: str, client: str = "Иванов Иван Иванович") -> Matter:
    now = datetime.now(timezone.utc)
    return Matter(
        id=matter_id,
        title=f"Дело {case_number}",
        matter_type=MatterType.GENERAL,
        client_name=client,
        case_number=case_number,
        created_at=now,
        updated_at=now,
    )


def test_exact_case_number_is_strong_match() -> None:
    result = MatterMatcher().best_match(
        "Судебное извещение по делу А40-12345/2026.",
        [matter("m1", case_number="А40-12345/2026"), matter("m2", case_number="А40-99999/2026")],
    )
    assert result is not None
    assert result.matter_id == "m1"
    assert "совпадает номер дела" in result.reasons


def test_ambiguous_candidates_fail_closed() -> None:
    matters = [
        matter("m1", case_number="А40-12345/2026", client="ООО Ромашка"),
        matter("m2", case_number="А40-99999/2026", client="ООО Ромашка"),
    ]
    assert MatterMatcher().best_match("Документы ООО Ромашка", matters) is None


def test_weak_signal_does_not_auto_attach() -> None:
    result = MatterMatcher().best_match(
        "Общие сведения без номера дела.",
        [matter("m1", case_number="А40-12345/2026")],
    )
    assert result is None


def test_candidates_are_deterministically_sorted() -> None:
    matters = [
        matter("m2", case_number="А40-22222/2026"),
        matter("m1", case_number="А40-11111/2026"),
    ]
    candidates = MatterMatcher().candidates(
        "Документы по А40-22222/2026 и А40-11111/2026", matters
    )
    assert [item.matter_id for item in candidates] == ["m1", "m2"]
