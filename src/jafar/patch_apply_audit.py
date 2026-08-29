from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any

from .lawyer_approval_patch import ControlledFragmentPatch
from .work_product_dependency_graph import WorkProductFragment


class PatchAuditEventType(StrEnum):
    APPLY = "apply"
    ROLLBACK = "rollback"


@dataclass(frozen=True, slots=True)
class PatchAuditEntry:
    entry_id: str
    event_type: PatchAuditEventType
    patch_id: str
    approval_id: str
    fragment_id: str
    work_product_id: str
    before_text_hash: str
    after_text_hash: str
    actor: str
    occurred_at: datetime
    authority_ids: tuple[str, ...]
    rule_ids: tuple[str, ...]
    previous_entry_hash: str
    entry_hash: str
    related_entry_id: str | None = None


@dataclass(frozen=True, slots=True)
class PatchApplyResult:
    fragment_before: WorkProductFragment
    fragment_after: WorkProductFragment
    audit_entry: PatchAuditEntry
    applied: bool = True


@dataclass(frozen=True, slots=True)
class PatchRollbackResult:
    fragment_before: WorkProductFragment
    fragment_after: WorkProductFragment
    audit_entry: PatchAuditEntry
    rolled_back_apply_entry_id: str
    rolled_back: bool = True


class PatchAuditLedger:
    """Append-only, hash-chained audit ledger for explicit fragment mutations."""

    def __init__(self) -> None:
        self._entries: list[PatchAuditEntry] = []

    def append(self, entry: PatchAuditEntry) -> None:
        expected_previous = self._entries[-1].entry_hash if self._entries else ""
        if entry.previous_entry_hash != expected_previous:
            raise ValueError("Audit entry previous hash does not match ledger head")
        if entry.entry_hash != self.compute_entry_hash(entry):
            raise ValueError("Audit entry hash is invalid")
        self._entries.append(entry)

    def entries(self) -> tuple[PatchAuditEntry, ...]:
        return tuple(self._entries)

    def last_hash(self) -> str:
        return self._entries[-1].entry_hash if self._entries else ""

    def get(self, entry_id: str) -> PatchAuditEntry | None:
        return next((entry for entry in self._entries if entry.entry_id == entry_id), None)

    def verify_chain(self) -> bool:
        previous = ""
        for entry in self._entries:
            if entry.previous_entry_hash != previous:
                return False
            if entry.entry_hash != self.compute_entry_hash(entry):
                return False
            previous = entry.entry_hash
        return True

    @classmethod
    def compute_entry_hash(cls, entry: PatchAuditEntry) -> str:
        raw = "\n".join(
            (
                entry.event_type.value,
                entry.patch_id,
                entry.approval_id,
                entry.fragment_id,
                entry.work_product_id,
                entry.before_text_hash,
                entry.after_text_hash,
                entry.actor,
                entry.occurred_at.isoformat(),
                "|".join(entry.authority_ids),
                "|".join(entry.rule_ids),
                entry.previous_entry_hash,
                entry.related_entry_id or "",
            )
        )
        return sha256(raw.encode("utf-8")).hexdigest()


class ControlledPatchApplyEngine:
    """Apply or roll back an approved fragment patch only after an explicit operation.

    The engine mutates no external file. It returns a new immutable WorkProductFragment
    snapshot plus an append-only audit entry. A storage/document adapter may persist the
    returned fragment only after the caller explicitly invokes this operation.
    """

    def __init__(self, ledger: PatchAuditLedger | None = None) -> None:
        self.ledger = ledger or PatchAuditLedger()

    def apply(
        self,
        *,
        fragment: WorkProductFragment,
        patch: ControlledFragmentPatch,
        applied_by: str,
        applied_at: datetime | None = None,
    ) -> PatchApplyResult:
        actor = self._actor(applied_by, "applied_by")
        timestamp = self._timestamp(applied_at)
        self._validate_patch_target(fragment, patch)

        before_hash = self._hash(fragment.text)
        if before_hash != patch.original_text_hash:
            raise ValueError("Current fragment no longer matches the patch original hash")
        if self._hash(patch.replacement_text) != patch.replacement_text_hash:
            raise ValueError("Patch replacement text hash is invalid")

        updated = replace(fragment, text=patch.replacement_text)
        after_hash = self._hash(updated.text)
        entry = self._entry(
            event_type=PatchAuditEventType.APPLY,
            patch=patch,
            before_hash=before_hash,
            after_hash=after_hash,
            actor=actor,
            occurred_at=timestamp,
        )
        self.ledger.append(entry)
        return PatchApplyResult(
            fragment_before=fragment,
            fragment_after=updated,
            audit_entry=entry,
        )

    def rollback(
        self,
        *,
        fragment: WorkProductFragment,
        patch: ControlledFragmentPatch,
        apply_entry_id: str,
        original_text: str,
        rolled_back_by: str,
        rolled_back_at: datetime | None = None,
    ) -> PatchRollbackResult:
        actor = self._actor(rolled_back_by, "rolled_back_by")
        timestamp = self._timestamp(rolled_back_at)
        self._validate_patch_target(fragment, patch)

        apply_entry = self.ledger.get(apply_entry_id)
        if apply_entry is None:
            raise ValueError("Apply audit entry was not found")
        if apply_entry.event_type != PatchAuditEventType.APPLY:
            raise ValueError("Rollback target must be an apply audit entry")
        if apply_entry.patch_id != patch.patch_id or apply_entry.fragment_id != fragment.fragment_id:
            raise ValueError("Apply audit entry does not belong to this patch/fragment")
        if self._hash(fragment.text) != apply_entry.after_text_hash:
            raise ValueError("Fragment changed after patch application; rollback would overwrite later edits")
        if self._hash(original_text) != patch.original_text_hash:
            raise ValueError("Rollback original text does not match the approved patch original hash")

        restored = replace(fragment, text=original_text)
        entry = self._entry(
            event_type=PatchAuditEventType.ROLLBACK,
            patch=patch,
            before_hash=self._hash(fragment.text),
            after_hash=self._hash(restored.text),
            actor=actor,
            occurred_at=timestamp,
            related_entry_id=apply_entry.entry_id,
        )
        self.ledger.append(entry)
        return PatchRollbackResult(
            fragment_before=fragment,
            fragment_after=restored,
            audit_entry=entry,
            rolled_back_apply_entry_id=apply_entry.entry_id,
        )

    @staticmethod
    def snapshot_entry(entry: PatchAuditEntry) -> dict[str, Any]:
        return {
            "entry_id": entry.entry_id,
            "event_type": entry.event_type.value,
            "patch_id": entry.patch_id,
            "approval_id": entry.approval_id,
            "fragment_id": entry.fragment_id,
            "work_product_id": entry.work_product_id,
            "before_text_hash": entry.before_text_hash,
            "after_text_hash": entry.after_text_hash,
            "actor": entry.actor,
            "occurred_at": entry.occurred_at.isoformat(),
            "authority_ids": list(entry.authority_ids),
            "rule_ids": list(entry.rule_ids),
            "previous_entry_hash": entry.previous_entry_hash,
            "entry_hash": entry.entry_hash,
            "related_entry_id": entry.related_entry_id,
        }

    def _entry(
        self,
        *,
        event_type: PatchAuditEventType,
        patch: ControlledFragmentPatch,
        before_hash: str,
        after_hash: str,
        actor: str,
        occurred_at: datetime,
        related_entry_id: str | None = None,
    ) -> PatchAuditEntry:
        previous = self.ledger.last_hash()
        seed = "\n".join(
            (
                event_type.value,
                patch.patch_id,
                patch.approval_id,
                patch.fragment_id,
                before_hash,
                after_hash,
                actor,
                occurred_at.isoformat(),
                previous,
                related_entry_id or "",
            )
        )
        entry_id = f"audit:{event_type.value}:{sha256(seed.encode('utf-8')).hexdigest()[:20]}"
        unsigned = PatchAuditEntry(
            entry_id=entry_id,
            event_type=event_type,
            patch_id=patch.patch_id,
            approval_id=patch.approval_id,
            fragment_id=patch.fragment_id,
            work_product_id=patch.work_product_id,
            before_text_hash=before_hash,
            after_text_hash=after_hash,
            actor=actor,
            occurred_at=occurred_at,
            authority_ids=patch.authority_ids,
            rule_ids=patch.rule_ids,
            previous_entry_hash=previous,
            entry_hash="",
            related_entry_id=related_entry_id,
        )
        return replace(unsigned, entry_hash=PatchAuditLedger.compute_entry_hash(unsigned))

    @staticmethod
    def _validate_patch_target(
        fragment: WorkProductFragment,
        patch: ControlledFragmentPatch,
    ) -> None:
        if patch.may_auto_apply:
            raise ValueError("Unsafe patch: automatic application is prohibited")
        if not patch.ready_for_explicit_apply:
            raise ValueError("Patch is not ready for explicit application")
        if fragment.fragment_id != patch.fragment_id:
            raise ValueError("Patch fragment_id does not match target fragment")
        if fragment.work_product_id != patch.work_product_id:
            raise ValueError("Patch work_product_id does not match target fragment")

    @staticmethod
    def _actor(value: str, field: str) -> str:
        actor = value.strip()
        if not actor:
            raise ValueError(f"{field} is required")
        return actor

    @staticmethod
    def _timestamp(value: datetime | None) -> datetime:
        timestamp = value or datetime.now(UTC)
        if timestamp.tzinfo is None:
            raise ValueError("Audit timestamp must be timezone-aware")
        return timestamp

    @staticmethod
    def _hash(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()
