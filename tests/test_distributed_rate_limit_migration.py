from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
BASE = ROOT / "20260828221000_add_distributed_ai_rate_limit.sql"
OWNER_SCOPE = ROOT / "20260828226000_scope_ai_rate_limit_to_owner.sql"


def test_rate_limit_storage_is_server_only_and_opaque() -> None:
    sql = BASE.read_text(encoding="utf-8").lower()

    assert "create table if not exists public.ai_rate_limit_buckets" in sql
    assert "key_hash text not null" in sql
    assert "key_hash ~ '^[0-9a-f]{64}$'" in sql
    assert "alter table public.ai_rate_limit_buckets enable row level security" in sql
    assert "revoke all on public.ai_rate_limit_buckets from anon, authenticated" in sql
    assert "to service_role" in sql


def test_effective_rate_limit_consume_is_atomic_bounded_and_owner_scoped() -> None:
    sql = OWNER_SCOPE.read_text(encoding="utf-8").lower()

    assert "p_owner_user_id text" in sql
    assert "add primary key (owner_user_id, key_hash, bucket_start, window_seconds)" in sql
    assert "on conflict (owner_user_id, key_hash, bucket_start, window_seconds)" in sql
    assert "request_count = public.ai_rate_limit_buckets.request_count + 1" in sql
    assert "where public.ai_rate_limit_buckets.request_count < p_max_requests" in sql
    assert "p_max_requests > 1000000" in sql
    assert "p_window_seconds > 86400" in sql
    assert "owner_user_id = btrim(p_owner_user_id)" in sql


def test_old_unscoped_rate_limit_rpcs_are_removed_and_replacements_are_service_role_only() -> None:
    sql = OWNER_SCOPE.read_text(encoding="utf-8").lower()

    assert "drop function if exists public.consume_ai_rate_limit(text, integer, integer)" in sql
    assert "drop function if exists public.cleanup_ai_rate_limit_buckets(integer)" in sql
    assert (
        "grant execute on function public.consume_ai_rate_limit(text, text, integer, integer) to service_role"
        in sql
    )
    assert (
        "grant execute on function public.cleanup_ai_rate_limit_buckets(text, integer) to service_role"
        in sql
    )
    assert "auth.role() <> 'service_role'" in sql
