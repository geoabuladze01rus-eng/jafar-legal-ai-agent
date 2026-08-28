from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .action_approval import ActionApprovalRepository, ActionApprovalStore
from .action_reconciliation import ReconciliationAuditRepository, ReconciliationAuditStore
from .config import Settings
from .matter_repository import MatterRepository
from .matters import MatterStore
from .supabase_action_approval import SupabaseActionApprovalRepository
from .supabase_config import SupabaseSettings, build_supabase_client
from .supabase_matter_repository import SupabaseMatterRepository
from .supabase_reconciliation_audit import SupabaseReconciliationAuditRepository


class StorageBackend(StrEnum):
    MEMORY = "memory"
    SUPABASE = "supabase"


@dataclass(frozen=True, slots=True)
class RuntimeRepositories:
    matters: MatterRepository
    approvals: ActionApprovalRepository
    reconciliation_audit: ReconciliationAuditRepository


def storage_backend(settings: Settings) -> StorageBackend:
    try:
        return StorageBackend(settings.storage_backend.strip().casefold())
    except ValueError as exc:
        raise RuntimeError(
            f"Unsupported STORAGE_BACKEND: {settings.storage_backend!r}"
        ) from exc


def validate_storage_security(settings: Settings) -> None:
    backend = storage_backend(settings)
    if (
        settings.environment.strip().casefold() == "production"
        and backend is StorageBackend.MEMORY
    ):
        raise RuntimeError(
            "Production requires persistent STORAGE_BACKEND=supabase; memory storage is ephemeral"
        )


def build_runtime_repositories(settings: Settings) -> RuntimeRepositories:
    backend = storage_backend(settings)
    if backend is StorageBackend.MEMORY:
        return RuntimeRepositories(
            matters=MatterStore(),
            approvals=ActionApprovalStore(),
            reconciliation_audit=ReconciliationAuditStore(),
        )

    client, owner_user_id = _supabase_context()
    return RuntimeRepositories(
        matters=SupabaseMatterRepository(
            client,
            owner_user_id,
            server_mode=True,
        ),
        approvals=SupabaseActionApprovalRepository(client, owner_user_id),
        reconciliation_audit=SupabaseReconciliationAuditRepository(client, owner_user_id),
    )


def build_matter_repository(settings: Settings) -> MatterRepository:
    return build_runtime_repositories(settings).matters


def build_action_approval_repository(settings: Settings) -> ActionApprovalRepository:
    return build_runtime_repositories(settings).approvals


def build_reconciliation_audit_repository(settings: Settings) -> ReconciliationAuditRepository:
    return build_runtime_repositories(settings).reconciliation_audit


def _supabase_context() -> tuple[Any, str]:
    supabase_settings = SupabaseSettings()
    owner_user_id = supabase_settings.require_owner_user_id()
    client = build_supabase_client(supabase_settings, server=True)
    return client, owner_user_id
