from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256

import pytest

from jafar.doctrine_case_impact import WorkProductKind
from jafar.lawyer_approval_patch import ControlledFragmentPatch
from jafar.patch_apply_audit import (
    ControlledPatchApplyEngine,
    PatchAuditEventType,
    PatchAuditLedger,
)
from jafar.work_product_dependency_graph import FragmentKind, WorkProductFragment


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _fragment(text: str = "Старый довод") -> WorkProductFragment:
    return WorkProductFragment(
        fragment_id="complaint:p3",
        work_product_id="complaint:1",
        work_product_kind=WorkProductKind.COMPLAINT,
        fragment_kind=FragmentKind.PARAGRAPH,
        ordinal=3,
        text=text,
        topic="допустимость доказательств",
        authority_ids=("authority:old",),
        rule_ids=("rule:old",),
        source_refs=("evidence:1",),
    )


def _patch(original: str = "Старый довод", replacement: str = "Новый проверенный довод") -> ControlledFragmentPatch:
    return ControlledFragmentPatch(
        patch_id="patch:complaint:p3:old:new",
        fragment_id="complaint:p3",
        work_product_id="complaint:1",
        original_text_hash=_hash(original),
        replacement_text=replacement,
        replacement_text_hash=_hash(replacement),
        approval_id="approval:1",
        proposal_hash="proposal-hash",
        authority_ids=("authority:new",),
        rule_ids=("rule:new",),
        ready_for_explicit_apply=True,
        may_auto_apply=False,
    )


def test_explicit_apply_returns_new_fragment_and_audit_entry() -> None:
    engine = ControlledPatchApplyEngine()
    result = engine.apply(
        fragment=_fragment(),
        patch=_patch(),
        applied_by="lawyer:chernov",
        applied_at=datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
    )

    assert result.fragment_before.text == "Старый довод"
    assert result.fragment_after.text == "Новый проверенный довод"
    assert result.audit_entry.event_type == PatchAuditEventType.APPLY
    assert result.audit_entry.approval_id == "approval:1"
    assert result.audit_entry.actor == "lawyer:chernov"
    assert engine.ledger.verify_chain() is True


def test_apply_refuses_stale_original_fragment() -> None:
    engine = ControlledPatchApplyEngine()
    with pytest.raises(ValueError, match="no longer matches"):
        engine.apply(
            fragment=_fragment("Абзац уже изменён вручную"),
            patch=_patch(),
            applied_by="lawyer:chernov",
        )


def test_apply_refuses_auto_apply_patch() -> None:
    engine = ControlledPatchApplyEngine()
    unsafe = replace(_patch(), may_auto_apply=True)
    with pytest.raises(ValueError, match="automatic application"):
        engine.apply(
            fragment=_fragment(),
            patch=unsafe,
            applied_by="lawyer:chernov",
        )


def test_apply_requires_identified_actor_and_timezone_aware_timestamp() -> None:
    engine = ControlledPatchApplyEngine()
    with pytest.raises(ValueError, match="applied_by"):
        engine.apply(fragment=_fragment(), patch=_patch(), applied_by="   ")

    with pytest.raises(ValueError, match="timezone-aware"):
        engine.apply(
            fragment=_fragment(),
            patch=_patch(),
            applied_by="lawyer:chernov",
            applied_at=datetime(2026, 8, 28, 12, 0),  # noqa: DTZ001
        )


def test_rollback_restores_exact_original_and_appends_linked_audit_entry() -> None:
    engine = ControlledPatchApplyEngine()
    applied = engine.apply(
        fragment=_fragment(),
        patch=_patch(),
        applied_by="lawyer:chernov",
        applied_at=datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
    )

    rolled_back = engine.rollback(
        fragment=applied.fragment_after,
        patch=_patch(),
        apply_entry_id=applied.audit_entry.entry_id,
        original_text="Старый довод",
        rolled_back_by="lawyer:chernov",
        rolled_back_at=datetime(2026, 8, 28, 12, 5, tzinfo=UTC),
    )

    assert rolled_back.fragment_after.text == "Старый довод"
    assert rolled_back.audit_entry.event_type == PatchAuditEventType.ROLLBACK
    assert rolled_back.audit_entry.related_entry_id == applied.audit_entry.entry_id
    assert len(engine.ledger.entries()) == 2
    assert engine.ledger.verify_chain() is True


def test_rollback_refuses_to_overwrite_later_manual_edit() -> None:
    engine = ControlledPatchApplyEngine()
    applied = engine.apply(
        fragment=_fragment(),
        patch=_patch(),
        applied_by="lawyer:chernov",
    )
    later_edit = replace(applied.fragment_after, text="Поздняя ручная редакция")

    with pytest.raises(ValueError, match="overwrite later edits"):
        engine.rollback(
            fragment=later_edit,
            patch=_patch(),
            apply_entry_id=applied.audit_entry.entry_id,
            original_text="Старый довод",
            rolled_back_by="lawyer:chernov",
        )


def test_rollback_requires_exact_original_text_bound_to_patch() -> None:
    engine = ControlledPatchApplyEngine()
    applied = engine.apply(
        fragment=_fragment(),
        patch=_patch(),
        applied_by="lawyer:chernov",
    )

    with pytest.raises(ValueError, match="original text"):
        engine.rollback(
            fragment=applied.fragment_after,
            patch=_patch(),
            apply_entry_id=applied.audit_entry.entry_id,
            original_text="Другой старый текст",
            rolled_back_by="lawyer:chernov",
        )


def test_audit_ledger_rejects_tampered_entry() -> None:
    ledger = PatchAuditLedger()
    engine = ControlledPatchApplyEngine(ledger)
    applied = engine.apply(
        fragment=_fragment(),
        patch=_patch(),
        applied_by="lawyer:chernov",
    )
    tampered = replace(applied.audit_entry, actor="other")

    second_ledger = PatchAuditLedger()
    with pytest.raises(ValueError, match="hash is invalid"):
        second_ledger.append(tampered)


def test_snapshot_contains_audit_provenance_without_raw_document_body() -> None:
    engine = ControlledPatchApplyEngine()
    result = engine.apply(
        fragment=_fragment(),
        patch=_patch(),
        applied_by="lawyer:chernov",
    )
    snapshot = engine.snapshot_entry(result.audit_entry)

    assert snapshot["approval_id"] == "approval:1"
    assert snapshot["fragment_id"] == "complaint:p3"
    assert snapshot["event_type"] == "apply"
    assert "Старый довод" not in str(snapshot)
    assert "Новый проверенный довод" not in str(snapshot)
