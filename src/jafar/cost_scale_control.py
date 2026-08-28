from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from threading import RLock
from typing import Any, Mapping, Protocol


MILLION = Decimal("1000000")


@dataclass(frozen=True, slots=True)
class ProviderPricing:
    """Configurable model pricing in USD per one million tokens.

    Pricing changes independently from application code. Production should build this catalog
    from reviewed configuration rather than embedding vendor prices in legal workflow logic.
    """

    input_per_million: Decimal
    output_per_million: Decimal
    cached_input_per_million: Decimal | None = None

    def __post_init__(self) -> None:
        values = (
            self.input_per_million,
            self.output_per_million,
            self.cached_input_per_million,
        )
        if any(value is not None and value < 0 for value in values):
            raise ValueError("provider_pricing_must_be_non_negative")


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0

    def __post_init__(self) -> None:
        if min(self.input_tokens, self.cached_input_tokens, self.output_tokens) < 0:
            raise ValueError("token_usage_must_be_non_negative")
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError("cached_input_tokens_cannot_exceed_input_tokens")

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @classmethod
    def from_provider_metadata(cls, metadata: Mapping[str, Any]) -> TokenUsage | None:
        """Normalize common provider usage shapes without retaining model output content."""

        usage = metadata.get("usage")
        if not isinstance(usage, Mapping):
            return None

        input_tokens = _first_int(usage, "input_tokens", "prompt_tokens")
        output_tokens = _first_int(usage, "output_tokens", "completion_tokens")
        cached_tokens = _cached_tokens(usage)
        if input_tokens is None and output_tokens is None and cached_tokens is None:
            return None

        normalized_input = max(input_tokens or 0, cached_tokens or 0)
        return cls(
            input_tokens=normalized_input,
            cached_input_tokens=cached_tokens or 0,
            output_tokens=output_tokens or 0,
        )


def _first_int(mapping: Mapping[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return None


def _cached_tokens(usage: Mapping[str, Any]) -> int | None:
    direct = _first_int(usage, "cached_input_tokens", "cache_read_input_tokens")
    if direct is not None:
        return direct
    for detail_key in ("input_tokens_details", "prompt_tokens_details"):
        details = usage.get(detail_key)
        if isinstance(details, Mapping):
            nested = _first_int(details, "cached_tokens", "cache_read_input_tokens")
            if nested is not None:
                return nested
    return None


def calculate_cost(usage: TokenUsage, pricing: ProviderPricing) -> Decimal:
    uncached_input = usage.input_tokens - usage.cached_input_tokens
    cached_rate = pricing.cached_input_per_million
    if cached_rate is None:
        cached_rate = pricing.input_per_million
    cost = (
        Decimal(uncached_input) * pricing.input_per_million
        + Decimal(usage.cached_input_tokens) * cached_rate
        + Decimal(usage.output_tokens) * pricing.output_per_million
    ) / MILLION
    return cost.quantize(Decimal("0.00000001"))


@dataclass(frozen=True, slots=True)
class UsageContext:
    request_id: str
    user_id: str
    operation: str
    matter_id: str | None = None

    def __post_init__(self) -> None:
        if not self.request_id.strip() or not self.user_id.strip() or not self.operation.strip():
            raise ValueError("usage_context_request_user_operation_required")


@dataclass(frozen=True, slots=True)
class CostRecord:
    context: UsageContext
    provider: str
    model: str
    usage: TokenUsage
    cost_usd: Decimal
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class BudgetLimits:
    per_request_usd: Decimal | None = None
    per_user_daily_usd: Decimal | None = None
    per_user_monthly_usd: Decimal | None = None
    global_daily_usd: Decimal | None = None

    def __post_init__(self) -> None:
        values = (
            self.per_request_usd,
            self.per_user_daily_usd,
            self.per_user_monthly_usd,
            self.global_daily_usd,
        )
        if any(value is not None and value <= 0 for value in values):
            raise ValueError("budget_limits_must_be_positive")


class CostLedgerRepository(Protocol):
    def record(self, record: CostRecord) -> None: ...

    def spend_for_user(self, user_id: str, *, since: datetime) -> Decimal: ...

    def spend_global(self, *, since: datetime) -> Decimal: ...


class CostLedger(CostLedgerRepository):
    """Thread-safe in-memory cost ledger for local development and tests."""

    def __init__(self) -> None:
        self._records: list[CostRecord] = []
        self._request_ids: set[str] = set()
        self._lock = RLock()

    def record(self, record: CostRecord) -> None:
        with self._lock:
            if record.context.request_id in self._request_ids:
                raise ValueError("duplicate_cost_request_id")
            self._request_ids.add(record.context.request_id)
            self._records.append(record)

    def records(self) -> tuple[CostRecord, ...]:
        with self._lock:
            return tuple(self._records)

    def spend_for_user(self, user_id: str, *, since: datetime) -> Decimal:
        return self._sum(
            since=since,
            predicate=lambda record: record.context.user_id == user_id,
        )

    def spend_global(self, *, since: datetime) -> Decimal:
        return self._sum(since=since, predicate=lambda _: True)

    def _sum(self, *, since: datetime, predicate) -> Decimal:
        if since.tzinfo is None:
            raise ValueError("since_must_be_timezone_aware")
        with self._lock:
            return sum(
                (
                    record.cost_usd
                    for record in self._records
                    if record.recorded_at >= since and predicate(record)
                ),
                Decimal("0"),
            )


class CostScaleControl:
    """Central metering, budget and provider-kill-switch boundary for model calls."""

    def __init__(
        self,
        *,
        pricing: Mapping[tuple[str, str], ProviderPricing],
        ledger: CostLedgerRepository | None = None,
        limits: BudgetLimits | None = None,
        fail_closed_on_missing_pricing: bool = True,
    ) -> None:
        self.pricing = dict(pricing)
        self.ledger = ledger or CostLedger()
        self.limits = limits or BudgetLimits()
        self.fail_closed_on_missing_pricing = fail_closed_on_missing_pricing
        self._disabled_providers: set[str] = set()
        self._lock = RLock()

    def disable_provider(self, provider: str) -> None:
        with self._lock:
            self._disabled_providers.add(provider.strip().casefold())

    def enable_provider(self, provider: str) -> None:
        with self._lock:
            self._disabled_providers.discard(provider.strip().casefold())

    def provider_enabled(self, provider: str) -> bool:
        with self._lock:
            return provider.strip().casefold() not in self._disabled_providers

    def preflight(self, context: UsageContext, *, estimated_cost_usd: Decimal) -> None:
        if estimated_cost_usd < 0:
            raise ValueError("estimated_cost_must_be_non_negative")
        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = day_start.replace(day=1)

        if self.limits.per_request_usd is not None:
            if estimated_cost_usd > self.limits.per_request_usd:
                raise RuntimeError("cost_budget_exceeded:per_request")
        if self.limits.per_user_daily_usd is not None:
            current = self.ledger.spend_for_user(context.user_id, since=day_start)
            if current + estimated_cost_usd > self.limits.per_user_daily_usd:
                raise RuntimeError("cost_budget_exceeded:user_daily")
        if self.limits.per_user_monthly_usd is not None:
            current = self.ledger.spend_for_user(context.user_id, since=month_start)
            if current + estimated_cost_usd > self.limits.per_user_monthly_usd:
                raise RuntimeError("cost_budget_exceeded:user_monthly")
        if self.limits.global_daily_usd is not None:
            current = self.ledger.spend_global(since=day_start)
            if current + estimated_cost_usd > self.limits.global_daily_usd:
                raise RuntimeError("cost_budget_exceeded:global_daily")

    def meter_response(
        self,
        *,
        context: UsageContext,
        provider: str,
        model: str,
        metadata: Mapping[str, Any],
    ) -> CostRecord | None:
        usage = TokenUsage.from_provider_metadata(metadata)
        if usage is None:
            if self.fail_closed_on_missing_pricing:
                raise RuntimeError("provider_usage_metadata_missing")
            return None

        pricing = self.pricing.get((provider, model)) or self.pricing.get((provider, "*"))
        if pricing is None:
            if self.fail_closed_on_missing_pricing:
                raise RuntimeError("provider_pricing_missing")
            return None

        record = CostRecord(
            context=context,
            provider=provider,
            model=model,
            usage=usage,
            cost_usd=calculate_cost(usage, pricing),
        )
        self.ledger.record(record)
        return record
