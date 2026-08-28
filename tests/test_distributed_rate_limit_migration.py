from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "20260828221000_add_distributed_ai_rate_limit.sql"
)


def test_rate_limit_storage_is_server_only_and_opaque() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create table if not exists public.ai_rate_limit_buckets" in sql
    assert "key_hash text not null" in sql
    assert "key_hash ~ '^[0-9a-f]{64}$'" in sql
    assert "alter table public.ai_rate_limit_buckets enable row level security" in sql
    assert "revoke all on public.ai_rate_limit_buckets from anon, authenticated" in sql
    assert "to service_role" in sql


def test_rate_limit_consume_is_atomic_and_bounded() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create or replace function public.consume_ai_rate_limit" in sql
    assert "on conflict (key_hash, bucket_start, window_seconds)" in sql
    assert "request_count = public.ai_rate_limit_buckets.request_count + 1" in sql
    assert "where public.ai_rate_limit_buckets.request_count < p_max_requests" in sql
    assert "p_max_requests > 1000000" in sql
    assert "p_window_seconds > 86400" in sql


def test_rate_limit_rpcs_are_service_role_only() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert (
        "revoke all on function public.consume_ai_rate_limit(text, integer, integer)"
        in sql
    )
    assert (
        "grant execute on function public.consume_ai_rate_limit(text, integer, integer) "
        "to service_role"
    ) in sql
    assert (
        "grant execute on function public.cleanup_ai_rate_limit_buckets(integer) "
        "to service_role"
    ) in sql
