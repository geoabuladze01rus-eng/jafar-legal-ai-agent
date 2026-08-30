from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

from .cost_scale_control import CostLedgerRepository, CostRecord


class SupabaseClient(Protocol):
    def table(self, name: str) -> Any: ...

    def rpc(self, function_name: str, params: dict[str, Any]) -> Any: ...


class SupabaseCostLedger(CostLedgerRepository):
    """Owner-scoped durable AI usage ledger for production cost enforcement."""

    TABLE = "ai_usage_costs"
    SPEND_RPC = "ai_spend_for_owner"
    MATTER_SPEND_RPC = "ai_spend_for_matter_for_owner"

    def __init__(self, client: SupabaseClient, owner_user_id: str) -> None:
        owner = owner_user_id.strip()
        if not owner:
            raise ValueError("owner_user_id_required")
        self.client = client
        self.owner_user_id = owner

    def record(self, record: CostRecord) -> None:
        payload = {
            "owner_user_id": self.owner_user_id,
            "request_id": record.context.request_id,
            "user_id": record.context.user_id,
            "matter_id": record.context.matter_id,
            "operation": record.context.operation,
            "provider": record.provider,
            "model": record.model,
            "pricing_version": record.pricing_version,
            "input_tokens": record.usage.input_tokens,
            "cached_input_tokens": record.usage.cached_input_tokens,
            "output_tokens": record.usage.output_tokens,
            "cost_usd": str(record.cost_usd),
            "recorded_at": record.recorded_at.isoformat(),
        }
        try:
            self.client.table(self.TABLE).insert(payload).execute()
        except Exception as exc:
            if self._request_exists(record.context.request_id):
                raise ValueError("duplicate_cost_request_id") from exc
            raise

    def spend_for_user(self, user_id: str, *, since: datetime) -> Decimal:
        return self._spend(since=since, user_id=user_id)

    def spend_for_matter(self, matter_id: str, *, since: datetime) -> Decimal:
        if since.tzinfo is None:
            raise ValueError("since_must_be_timezone_aware")
        normalized_matter = matter_id.strip()
        if not normalized_matter:
            raise ValueError("matter_id_required")
        response = self.client.rpc(
            self.MATTER_SPEND_RPC,
            {
                "p_owner_user_id": self.owner_user_id,
                "p_matter_id": normalized_matter,
                "p_since": since.isoformat(),
            },
        ).execute()
        return _decimal_response(response.data, self.MATTER_SPEND_RPC)

    def spend_global(self, *, since: datetime) -> Decimal:
        return self._spend(since=since, user_id=None)

    def _spend(self, *, since: datetime, user_id: str | None) -> Decimal:
        if since.tzinfo is None:
            raise ValueError("since_must_be_timezone_aware")
        response = self.client.rpc(
            self.SPEND_RPC,
            {
                "p_owner_user_id": self.owner_user_id,
                "p_user_id": user_id,
                "p_since": since.isoformat(),
            },
        ).execute()
        return _decimal_response(response.data, self.SPEND_RPC)

    def _request_exists(self, request_id: str) -> bool:
        response = (
            self.client.table(self.TABLE)
            .select("request_id")
            .eq("owner_user_id", self.owner_user_id)
            .eq("request_id", request_id)
            .maybe_single()
            .execute()
        )
        return bool(response.data)


def _decimal_response(value: Any, rpc_name: str) -> Decimal:
    if isinstance(value, list):
        value = value[0] if value else 0
        if isinstance(value, dict):
            value = value.get(rpc_name, 0)
    if isinstance(value, dict):
        value = value.get(rpc_name, 0)
    return Decimal(str(value or 0))
