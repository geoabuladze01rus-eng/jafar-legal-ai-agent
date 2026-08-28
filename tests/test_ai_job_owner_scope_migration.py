from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/20260828223000_scope_ai_job_rpcs_to_owner.sql"
)


def test_ai_job_queue_rpcs_are_owner_scoped_and_old_bypass_signatures_removed() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").casefold()

    assert "drop function if exists public.claim_ai_jobs(text, integer)" in sql
    assert "drop function if exists public.mark_ai_job_dispatched(text, text)" in sql
    assert "drop function if exists public.reclaim_stale_undispatched_ai_jobs(integer, integer)" in sql
    assert "drop function if exists public.finish_ai_job(text, text, boolean, text, integer)" in sql

    assert "p_owner_id text" in sql
    assert "j.owner_id = btrim(p_owner_id)" in sql
    assert "owner_id = btrim(p_owner_id)" in sql
    assert "grant execute on function public.claim_ai_jobs(text, text, integer) to service_role" in sql
    assert "from public, anon, authenticated" in sql
