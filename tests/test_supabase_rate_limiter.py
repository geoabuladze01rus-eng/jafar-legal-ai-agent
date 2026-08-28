from __future__ import annotations

import hashlib

import pytest

from jafar.scale_runtime import RateLimitPolicy
from jafar.supabase_rate_limiter import SupabaseRateLimiter


class _Response:
    def __init__(self, data):
        self.data = data


class _Action:
    def __init__(self, client, name, payload):
        self.client = client
        self.name = name
        self.payload = payload

    def execute(self):
        self.client.calls.append((self.name, self.payload))
        if self.name == "consume_ai_rate_limit":
            return _Response(True)
        if self.name == "cleanup_ai_rate_limit_buckets":
            return _Response(7)
        return _Response(None)


class _Client:
    def __init__(self):
        self.calls = []

    def rpc(self, name, payload):
        return _Action(self, name, payload)


def test_rate_limiter_hashes_raw_identity_before_database_call() -> None:
    client = _Client()
    limiter = SupabaseRateLimiter(
        client,
        RateLimitPolicy(max_requests=20, window_seconds=60),
        namespace="analysis",
    )

    assert limiter.allow("lawyer-secret-id") is True
    name, payload = client.calls[-1]
    assert name == "consume_ai_rate_limit"
    assert payload["p_key_hash"] == hashlib.sha256(
        b"analysis:lawyer-secret-id"
    ).hexdigest()
    assert "lawyer-secret-id" not in repr(payload)
    assert payload["p_max_requests"] == 20
    assert payload["p_window_seconds"] == 60


def test_rate_limiter_rejects_non_integral_or_extreme_policy() -> None:
    client = _Client()
    with pytest.raises(ValueError, match="whole_seconds"):
        SupabaseRateLimiter(client, RateLimitPolicy(max_requests=1, window_seconds=0.5))
    with pytest.raises(ValueError, match="too_large"):
        SupabaseRateLimiter(client, RateLimitPolicy(max_requests=1, window_seconds=86401))
    with pytest.raises(ValueError, match="max_requests_too_large"):
        SupabaseRateLimiter(client, RateLimitPolicy(max_requests=1000001, window_seconds=60))


def test_cleanup_retention_is_bounded() -> None:
    client = _Client()
    limiter = SupabaseRateLimiter(client, RateLimitPolicy(max_requests=5, window_seconds=60))

    assert limiter.cleanup(retention_seconds=1) == 7
    assert client.calls[-1] == (
        "cleanup_ai_rate_limit_buckets",
        {"p_retention_seconds": 86400},
    )
