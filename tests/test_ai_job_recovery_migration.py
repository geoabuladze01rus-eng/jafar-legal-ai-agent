from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "20260828222000_harden_ai_job_recovery.sql"
)


def test_provider_dispatch_is_recorded_before_unsafe_replay_boundary() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "provider_dispatch_started_at timestamptz" in sql
    assert "create or replace function public.mark_ai_job_dispatched" in sql
    assert "state = 'running'" in sql
    assert "claimed_by = btrim(p_worker_id)" in sql
    assert "provider_dispatch_started_at = coalesce(provider_dispatch_started_at, now())" in sql


def test_automatic_reclaim_is_limited_to_never_dispatched_jobs() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create or replace function public.reclaim_stale_undispatched_ai_jobs" in sql
    assert "provider_dispatch_started_at is null" in sql
    assert "claimed_at < now() - make_interval" in sql
    assert "for update skip locked" in sql
    assert "stale_claim_recovered_before_dispatch" in sql


def test_post_dispatch_recovery_rpcs_are_service_role_only() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "revoke all on function public.mark_ai_job_dispatched(text, text)" in sql
    assert (
        "grant execute on function public.mark_ai_job_dispatched(text, text) to service_role"
        in sql
    )
    assert (
        "grant execute on function public.reclaim_stale_undispatched_ai_jobs(integer, integer) "
        "to service_role"
    ) in sql
