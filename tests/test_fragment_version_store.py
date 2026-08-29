from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256

import pytest

from jafar.doctrine_case_impact import WorkProductKind
from jafar.fragment_version_store import ExplicitPatchMutationService, FragmentVersionStore
from jafar.lawyer_approval_patch import ControlledFragmentPatch
from jafar.work_product_dependency_graph import FragmentKind, WorkProductFragment


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _fragment(text: str = "Старый довод") -> WorkProductFragment:
    return WorkProductFragment(
        fragment_id="motion:p2",
        work_product_id="motion:1",
        work_product_kind=WorkProductKind.MOTION,
        fragment_kind=FragmentKind.ARGUMENT,
        ordinal=2,
        text=text,
        topic="меры пресечения",
        authority_ids=("authority:old",),
        rule_ids=("rule:old",),
        source_refs=("evidence:2",),
    )


def _patch() -> ControlledFragmentPatch:
    return ControlledFragmentPatch(
        patch_id="patch:motion:p2:old:new",
        fragment_id="motion:p2",
        work_product_id="motion:1",
        original_text_hash=_hash("Старый довод"),
        replacement_text="Новый проверенный довод",
        replacement_text_hash=_hash("Новый проверенный довод"),
        approval_id="approval:motion:1",
        proposal_hash="proposal:motion:1",
        authority_ids=("authority:new",),
        rule_ids=("rule:new",),
        ready_for_explicit_apply=True,
        may_auto_apply=False,
    )


def test_seed_creates_immutable_initial_version() -> None:
    store = FragmentVersionStore()
    version = store.seed(
        fragment=_fragment(),
        created_by="lawyer:chernov",
        created_at=datetime(2026, 8, 28, 13, 0, tzinfo=UTC),
    )

    assert version.version_number == 1
    assert version.event_type == "seed"
    assert version.text == "Старый довод"
    assert version.parent_version_id is None
    assert store.current("motion:p2") == _fragment()


def test_explicit_service_persists_new_version_and_keeps_original_history() -> None:
    service = ExplicitPatchMutationService()
    initial = service.store.seed(
        fragment=_fragment(),
        created_by="lawyer:chernov",
        created_at=datetime(2026, 8, 28, 13, 0, tzinfo=UTC),
    )

    applied, version = service.apply(
        patch=_patch(),
        applied_by="lawyer:chernov",
        applied_at=datetime(2026, 8, 28, 13, 5, tzinfo=UTC),
    )

    assert applied.fragment_after.text == "Новый проверенный довод"
    assert version.version_number == 2
    assert version.parent_version_id == initial.version_id
    assert version.approval_id == "approval:motion:1"
    assert version.audit_entry_id == applied.audit_entry.entry_id
    assert [item.text for item in service.store.versions("motion:p2")] == [
        "Старый довод",
        "Новый проверенный довод",
    ]


def test_rollback_creates_third_version_instead_of_deleting_history() -> None:
    service = ExplicitPatchMutationService()
    service.store.seed(fragment=_fragment(), created_by="lawyer:chernov")
    applied, _ = service.apply(patch=_patch(), applied_by="lawyer:chernov")

    rolled_back, version = service.rollback(
        patch=_patch(),
        apply_entry_id=applied.audit_entry.entry_id,
        original_text="Старый довод",
        rolled_back_by="lawyer:chernov",
    )

    assert rolled_back.fragment_after.text == "Старый довод"
    assert version.version_number == 3
    assert version.event_type == "rollback"
    assert [item.text for item in service.store.versions("motion:p2")] == [
        "Старый довод",
        "Новый проверенный довод",
        "Старый довод",
    ]
    assert service.apply_engine.ledger.verify_chain() is True


def test_store_refuses_mutation_when_current_snapshot_diverges() -> None:
    store = FragmentVersionStore()
    store.seed(fragment=_fragment(), created_by="lawyer:chernov")
    service = ExplicitPatchMutationService(store=store)
    applied = service.apply_engine.apply(
        fragment=_fragment(),
        patch=_patch(),
        applied_by="lawyer:chernov",
    )
    store._fragments["motion:p2"] = replace(_fragment(), text="Внешняя правка")

    with pytest.raises(ValueError, match="differs from mutation input"):
        store.record_apply(applied)


def test_service_requires_seeded_fragment() -> None:
    service = ExplicitPatchMutationService()
    with pytest.raises(ValueError, match="not present"):
        service.apply(patch=_patch(), applied_by="lawyer:chernov")


def test_seed_rejects_duplicate_fragment_and_naive_timestamp() -> None:
    store = FragmentVersionStore()
    store.seed(fragment=_fragment(), created_by="lawyer:chernov")
    with pytest.raises(ValueError, match="already been seeded"):
        store.seed(fragment=_fragment(), created_by="lawyer:chernov")

    second = FragmentVersionStore()
    with pytest.raises(ValueError, match="timezone-aware"):
        second.seed(
            fragment=_fragment(),
            created_by="lawyer:chernov",
            created_at=datetime(2026, 8, 28, 13, 0),  # noqa: DTZ001
        )
