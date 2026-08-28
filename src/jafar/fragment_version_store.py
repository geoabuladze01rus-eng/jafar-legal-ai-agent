from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256

from .lawyer_approval_patch import ControlledFragmentPatch
from .patch_apply_audit import (
    ControlledPatchApplyEngine,
    PatchApplyResult,
    PatchAuditEventType,
    PatchRollbackResult,
)
from .work_product_dependency_graph import WorkProductFragment


@dataclass(frozen=True, slots=True)
class FragmentVersion:
    version_id: str
    fragment_id: str
    work_product_id: str
    version_number: int
    text: str
    text_hash: str
    created_by: str
    created_at: datetime
    event_type: str
    audit_entry_id: str | None
    approval_id: str | None
    parent_version_id: str | None


class FragmentVersionStore:
    """In-memory contract for immutable fragment versions.

    Production storage can implement the same semantics in a database or document store.
    Audit entries intentionally keep hashes only; this store is where versioned legal text
    lives and therefore must use the deployment's privileged/confidential storage policy.
    """

    def __init__(self) -> None:
        self._versions: dict[str, list[FragmentVersion]] = {}
        self._fragments: dict[str, WorkProductFragment] = {}

    def seed(
        self,
        *,
        fragment: WorkProductFragment,
        created_by: str,
        created_at: datetime | None = None,
    ) -> FragmentVersion:
        if fragment.fragment_id in self._versions:
            raise ValueError("Fragment has already been seeded")
        actor = self._actor(created_by)
        timestamp = self._timestamp(created_at)
        version = self._version(
            fragment=fragment,
            version_number=1,
            actor=actor,
            occurred_at=timestamp,
            event_type="seed",
            audit_entry_id=None,
            approval_id=None,
            parent_version_id=None,
        )
        self._versions[fragment.fragment_id] = [version]
        self._fragments[fragment.fragment_id] = fragment
        return version

    def current(self, fragment_id: str) -> WorkProductFragment | None:
        return self._fragments.get(fragment_id)

    def latest_version(self, fragment_id: str) -> FragmentVersion | None:
        versions = self._versions.get(fragment_id, [])
        return versions[-1] if versions else None

    def versions(self, fragment_id: str) -> tuple[FragmentVersion, ...]:
        return tuple(self._versions.get(fragment_id, []))

    def record_apply(self, result: PatchApplyResult) -> FragmentVersion:
        return self._record_mutation(
            before=result.fragment_before,
            after=result.fragment_after,
            actor=result.audit_entry.actor,
            occurred_at=result.audit_entry.occurred_at,
            event_type=PatchAuditEventType.APPLY.value,
            audit_entry_id=result.audit_entry.entry_id,
            approval_id=result.audit_entry.approval_id,
        )

    def record_rollback(self, result: PatchRollbackResult) -> FragmentVersion:
        return self._record_mutation(
            before=result.fragment_before,
            after=result.fragment_after,
            actor=result.audit_entry.actor,
            occurred_at=result.audit_entry.occurred_at,
            event_type=PatchAuditEventType.ROLLBACK.value,
            audit_entry_id=result.audit_entry.entry_id,
            approval_id=result.audit_entry.approval_id,
        )

    def _record_mutation(
        self,
        *,
        before: WorkProductFragment,
        after: WorkProductFragment,
        actor: str,
        occurred_at: datetime,
        event_type: str,
        audit_entry_id: str,
        approval_id: str,
    ) -> FragmentVersion:
        current = self.current(before.fragment_id)
        latest = self.latest_version(before.fragment_id)
        if current is None or latest is None:
            raise ValueError("Fragment must be seeded before mutation")
        if current != before:
            raise ValueError("Version store current fragment differs from mutation input")
        if latest.text_hash != self._hash(before.text):
            raise ValueError("Version store history does not match current fragment")

        version = self._version(
            fragment=after,
            version_number=latest.version_number + 1,
            actor=actor,
            occurred_at=occurred_at,
            event_type=event_type,
            audit_entry_id=audit_entry_id,
            approval_id=approval_id,
            parent_version_id=latest.version_id,
        )
        self._versions[after.fragment_id].append(version)
        self._fragments[after.fragment_id] = after
        return version

    @classmethod
    def _version(
        cls,
        *,
        fragment: WorkProductFragment,
        version_number: int,
        actor: str,
        occurred_at: datetime,
        event_type: str,
        audit_entry_id: str | None,
        approval_id: str | None,
        parent_version_id: str | None,
    ) -> FragmentVersion:
        text_hash = cls._hash(fragment.text)
        seed = "\n".join(
            (
                fragment.fragment_id,
                str(version_number),
                text_hash,
                actor,
                occurred_at.isoformat(),
                event_type,
                audit_entry_id or "",
                approval_id or "",
                parent_version_id or "",
            )
        )
        version_id = f"fragment-version:{sha256(seed.encode('utf-8')).hexdigest()[:24]}"
        return FragmentVersion(
            version_id=version_id,
            fragment_id=fragment.fragment_id,
            work_product_id=fragment.work_product_id,
            version_number=version_number,
            text=fragment.text,
            text_hash=text_hash,
            created_by=actor,
            created_at=occurred_at,
            event_type=event_type,
            audit_entry_id=audit_entry_id,
            approval_id=approval_id,
            parent_version_id=parent_version_id,
        )

    @staticmethod
    def _actor(value: str) -> str:
        actor = value.strip()
        if not actor:
            raise ValueError("created_by is required")
        return actor

    @staticmethod
    def _timestamp(value: datetime | None) -> datetime:
        timestamp = value or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return timestamp

    @staticmethod
    def _hash(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()


class ExplicitPatchMutationService:
    """Explicitly apply/rollback controlled patches against a versioned fragment store."""

    def __init__(
        self,
        *,
        store: FragmentVersionStore | None = None,
        apply_engine: ControlledPatchApplyEngine | None = None,
    ) -> None:
        self.store = store or FragmentVersionStore()
        self.apply_engine = apply_engine or ControlledPatchApplyEngine()

    def apply(
        self,
        *,
        patch: ControlledFragmentPatch,
        applied_by: str,
        applied_at: datetime | None = None,
    ) -> tuple[PatchApplyResult, FragmentVersion]:
        current = self.store.current(patch.fragment_id)
        if current is None:
            raise ValueError("Target fragment is not present in the version store")
        result = self.apply_engine.apply(
            fragment=current,
            patch=patch,
            applied_by=applied_by,
            applied_at=applied_at,
        )
        version = self.store.record_apply(result)
        return result, version

    def rollback(
        self,
        *,
        patch: ControlledFragmentPatch,
        apply_entry_id: str,
        original_text: str,
        rolled_back_by: str,
        rolled_back_at: datetime | None = None,
    ) -> tuple[PatchRollbackResult, FragmentVersion]:
        current = self.store.current(patch.fragment_id)
        if current is None:
            raise ValueError("Target fragment is not present in the version store")
        result = self.apply_engine.rollback(
            fragment=current,
            patch=patch,
            apply_entry_id=apply_entry_id,
            original_text=original_text,
            rolled_back_by=rolled_back_by,
            rolled_back_at=rolled_back_at,
        )
        version = self.store.record_rollback(result)
        return result, version
