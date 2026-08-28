from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Protocol

from .cost_scale_control import BudgetLimits, UsageContext


class SupabaseClient(Protocol):
    def rpc(self, function_name: str, params: dict[str, Any]) -> Any: ...


@dataclass(frozen=True, slots=True)
class CostReservation:
    reservation_id: str
    context: UsageContext
    estimated_cost_usd: Decimal
    expires_at: datetime


class SupabaseCostReservationRepository:
    """Atomic cross-process spend reservation using server-only Supabase RPCs."""

    RESERVE_RPC = "reserve_ai_cost_for_owner"
    CLOSE_RPC = "close_ai_cost_reservation_for_owner"

    def __init__(self, client: SupabaseClient, owner_user_id: str) -> None:
        owner = owner_user_id.strip()
        if not owner:
            raise ValueError("owner_user_id_required")
        self.client = client
        self.owner_user_id = owner

    def reserve(
        self,
        *,
        context: UsageContext,
        estimated_cost_usd: Decimal,
        limits: BudgetLimits,
        ttl_seconds: int = 300,
    ) -> CostReservation:
        if estimated_cost_usd < 0:
            raise ValueError("estimated_cost_must_be_non_negative")
        if ttl_seconds <= 0:
            raise ValueError("reservation_ttl_must_be_positive")
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        response = self.client.rpc(
            self.RESERVE_RPC,
            {
                "p_owner_user_id": self.owner_user_id,
                "p_reservation_id": context.request_id,
                "p_user_id": context.user_id,
                "p_matter_id": context.matter_id or "",
                "p_operation": context.operation,
                "p_estimated_cost_usd": str(estimated_cost_usd),
                "p_expires_at": expires_at.isoformat(),
                "p_user_daily_limit_usd": _decimal_or_none(limits.per_user_daily_usd),
                "p_user_monthly_limit_usd": _decimal_or_none(limits.per_user_monthly_usd),
                "p_global_daily_limit_usd": _decimal_or_none(limits.global_daily_usd),
            },
        ).execute()
        if response.data is None:
            raise RuntimeError("cost_reservation_failed")
        return CostReservation(
            reservation_id=context.request_id,
            context=context,
            estimated_cost_usd=estimated_cost_usd,
            expires_at=expires_at,
        )

    def release(self, reservation_id: str) -> None:
        self._close(reservation_id, "released")

    def settle(self, reservation_id: str) -> None:
        self._close(reservation_id, "settled")

    def _close(self, reservation_id: str, state: str) -> None:
        reservation = reservation_id.strip()
        if not reservation:
            raise ValueError("reservation_id_required")
        response = self.client.rpc(
            self.CLOSE_RPC,
            {
                "p_owner_user_id": self.owner_user_id,
                "p_reservation_id": reservation,
                "p_state": state,
            },
        ).execute()
        if response.data is False:
            raise RuntimeError("cost_reservation_not_active")


def _decimal_or_none(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None
