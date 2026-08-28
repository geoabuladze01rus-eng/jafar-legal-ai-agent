from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "20260828220000_add_ai_job_queue.sql"
)


def test_ai_queue_is_server_only_and_claims_with_skip_locked() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create table if not exists public.ai_jobs" in sql
    assert "alter table public.ai_jobs enable row level security" in sql
    assert "revoke all on public.ai_jobs from anon, authenticated" in sql
    assert "grant select, insert, update, delete on public.ai_jobs to service_role" in sql
    assert "for update skip locked" in sql
    assert "security definer" in sql
    assert "set search_path = public, pg_temp" in sql


def test_ai_queue_rpc_permissions_are_service_role_only() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert (
        "revoke all on function public.claim_ai_jobs(text, integer) "
        "from public, anon, authenticated"
    ) in sql
    assert "grant execute on function public.claim_ai_jobs(text, integer) to service_role" in sql
    assert (
        "revoke all on function public.finish_ai_job(text, text, boolean, text, integer) "
        "from public, anon, authenticated"
    ) in sql
    assert (
        "grant execute on function public.finish_ai_job(text, text, boolean, text, integer) "
        "to service_role"
    ) in sql


def test_ai_queue_has_bounded_retry_and_dead_letter_state() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "'dead'" in sql
    assert "max_attempts between 1 and 20" in sql
    assert "attempts < j.max_attempts" in sql
    assert "current_job.attempts >= current_job.max_attempts" in sql
    assert "greatest(0, least(coalesce(p_retry_after_seconds, 0), 86400))" in sql
