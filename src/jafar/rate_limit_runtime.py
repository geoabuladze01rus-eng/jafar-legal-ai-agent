from __future__ import annotations

from typing import Protocol

from .config import Settings
from .scale_runtime import RateLimitPolicy, SlidingWindowRateLimiter
from .supabase_config import SupabaseSettings, build_supabase_client
from .supabase_rate_limiter import SupabaseRateLimiter


class RateLimiter(Protocol):
    def allow(self, key: str) -> bool: ...


def build_ai_rate_limiter(settings: Settings) -> RateLimiter:
    policy = RateLimitPolicy(
        max_requests=settings.ai_rate_limit_requests,
        window_seconds=settings.ai_rate_limit_window_seconds,
    )
    if settings.environment.strip().casefold() == "production":
        supabase_settings = SupabaseSettings()
        owner_user_id = supabase_settings.require_owner_user_id()
        client = build_supabase_client(supabase_settings, server=True)
        return SupabaseRateLimiter(
            client,
            policy,
            owner_user_id=owner_user_id,
            namespace="api-ai",
        )
    return SlidingWindowRateLimiter(policy)
