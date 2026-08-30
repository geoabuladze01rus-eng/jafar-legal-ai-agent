from __future__ import annotations

from typing import Any, Protocol

from .config import Settings
from .scale_runtime import BoundedPriorityQueue, QueueJob
from .supabase_ai_job_queue import SupabaseAIJobQueue
from .supabase_config import SupabaseSettings, build_supabase_client


class AIQueue(Protocol):
    """Minimal enqueue boundary shared by local and production queue backends."""

    def enqueue(
        self,
        *,
        job_id: str,
        owner_id: str,
        operation: str,
        payload: dict[str, Any],
        priority: int = 100,
        max_attempts: int = 3,
    ) -> None: ...


class LocalAIJobQueue:
    """Development-only adapter over the in-process bounded queue."""

    def __init__(self, *, max_size: int, max_per_user: int) -> None:
        self.queue: BoundedPriorityQueue[dict[str, Any]] = BoundedPriorityQueue(
            max_size=max_size,
            max_per_user=max_per_user,
        )

    def enqueue(
        self,
        *,
        job_id: str,
        owner_id: str,
        operation: str,
        payload: dict[str, Any],
        priority: int = 100,
        max_attempts: int = 3,
    ) -> None:
        if max_attempts != 3:
            # The local queue intentionally has no durable retry ledger. Keep its semantics
            # narrow so development cannot imply production-grade recovery guarantees.
            raise ValueError("local_ai_queue_fixed_retry_policy")
        self.queue.enqueue(
            QueueJob(
                job_id=job_id,
                user_id=owner_id,
                operation=operation,
                payload=payload,
                priority=priority,
            )
        )


def build_ai_queue(settings: Settings) -> AIQueue:
    backend = settings.ai_queue_backend.strip().casefold()
    production = settings.environment.strip().casefold() == "production"

    if production and backend != "supabase":
        raise RuntimeError("Production AI queue requires durable Supabase backend")

    if backend == "supabase":
        supabase_settings = SupabaseSettings()
        owner_user_id = supabase_settings.require_owner_user_id()
        client = build_supabase_client(supabase_settings, server=True)
        return SupabaseAIJobQueue(client, owner_user_id)

    if backend == "memory" and not production:
        return LocalAIJobQueue(
            max_size=max(1, settings.ai_queue_max_size),
            max_per_user=max(1, settings.ai_queue_max_per_user),
        )

    raise RuntimeError(f"Unsupported AI queue backend: {backend or '<empty>'}")
