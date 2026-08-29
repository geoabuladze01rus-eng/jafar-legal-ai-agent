from __future__ import annotations

import hashlib

from .scale_runtime import RateLimitPolicy


class SupabaseRateLimiter:
    """Owner-scoped distributed rate limiter for horizontally scaled deployments.

    The database receives only SHA-256 keys plus the server-controlled owner identity. Raw user
    IDs, matter IDs, prompts and legal content must never be durable rate-limit dimensions.
    """

    def __init__(
        self,
        client: object,
        policy: RateLimitPolicy,
        *,
        owner_user_id: str,
        namespace: str = "ai",
    ) -> None:
        owner = owner_user_id.strip()
        if not owner:
            raise ValueError("rate_limit_owner_required")
        if not namespace.strip():
            raise ValueError("rate_limit_namespace_required")
        if policy.window_seconds < 1 or not float(policy.window_seconds).is_integer():
            raise ValueError("distributed_rate_limit_window_must_be_whole_seconds")
        if policy.window_seconds > 86400:
            raise ValueError("distributed_rate_limit_window_too_large")
        if policy.max_requests > 1000000:
            raise ValueError("distributed_rate_limit_max_requests_too_large")
        self.client = client
        self.policy = policy
        self.owner_user_id = owner
        self.namespace = namespace.strip()

    def allow(self, key: str) -> bool:
        if not key.strip():
            raise ValueError("rate_limit_key_required")
        key_hash = hashlib.sha256(
            f"{self.namespace}:{key.strip()}".encode()
        ).hexdigest()
        response = self.client.rpc(
            "consume_ai_rate_limit",
            {
                "p_owner_user_id": self.owner_user_id,
                "p_key_hash": key_hash,
                "p_max_requests": self.policy.max_requests,
                "p_window_seconds": int(self.policy.window_seconds),
            },
        ).execute()
        value = response.data
        if isinstance(value, list):
            value = value[0] if value else None
        if not isinstance(value, bool):
            raise RuntimeError("rate_limit_response_invalid")  # noqa: TRY004
        return value

    def cleanup(self, *, retention_seconds: int = 172800) -> int:
        retention = max(86400, min(int(retention_seconds), 2592000))
        response = self.client.rpc(
            "cleanup_ai_rate_limit_buckets",
            {
                "p_owner_user_id": self.owner_user_id,
                "p_retention_seconds": retention,
            },
        ).execute()
        value = response.data
        if isinstance(value, list):
            value = value[0] if value else None
        if isinstance(value, bool) or not isinstance(value, int):
            raise RuntimeError("rate_limit_cleanup_response_invalid")  # noqa: TRY004
        return value
