-- Owner-scope every durable AI queue transition.
-- A shared service-role worker must not accidentally claim or mutate another owner's jobs.
-- Replace the earlier unscoped RPC signatures rather than leaving a bypass callable.

drop function if exists public.claim_ai_jobs(text, integer);
drop function if exists public.mark_ai_job_dispatched(text, text);
drop function if exists public.reclaim_stale_undispatched_ai_jobs(integer, integer);
drop function if exists public.finish_ai_job(text, text, boolean, text, integer);

create or replace function public.claim_ai_jobs(
    p_owner_id text,
    p_worker_id text,
    p_limit integer default 5
)
returns setof public.ai_jobs
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
    if nullif(btrim(p_owner_id), '') is null then
        raise exception 'owner_id_required';
    end if;
    if nullif(btrim(p_worker_id), '') is null then
        raise exception 'worker_id_required';
    end if;

    return query
    with candidates as (
        select j.id
        from public.ai_jobs j
        where j.owner_id = btrim(p_owner_id)
          and j.state = 'queued'
          and j.available_at <= now()
          and j.attempts < j.max_attempts
        order by j.priority asc, j.created_at asc, j.id asc
        for update skip locked
        limit greatest(1, least(coalesce(p_limit, 5), 50))
    ), claimed as (
        update public.ai_jobs j
        set state = 'running',
            attempts = j.attempts + 1,
            claimed_at = now(),
            claimed_by = btrim(p_worker_id),
            last_error_code = null,
            updated_at = now()
        from candidates c
        where j.id = c.id
          and j.owner_id = btrim(p_owner_id)
        returning j.*
    )
    select * from claimed;
end;
$$;

create or replace function public.mark_ai_job_dispatched(
    p_owner_id text,
    p_id text,
    p_worker_id text
)
returns public.ai_jobs
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    current_job public.ai_jobs;
begin
    if nullif(btrim(p_owner_id), '') is null then
        raise exception 'owner_id_required';
    end if;

    update public.ai_jobs
    set provider_dispatch_started_at = coalesce(provider_dispatch_started_at, now()),
        updated_at = now()
    where id = p_id
      and owner_id = btrim(p_owner_id)
      and state = 'running'
      and claimed_by = btrim(p_worker_id)
    returning * into current_job;

    if not found then
        raise exception 'ai_job_claim_mismatch';
    end if;
    return current_job;
end;
$$;

create or replace function public.reclaim_stale_undispatched_ai_jobs(
    p_owner_id text,
    p_stale_seconds integer default 300,
    p_limit integer default 50
)
returns integer
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    reclaimed_count integer;
begin
    if nullif(btrim(p_owner_id), '') is null then
        raise exception 'owner_id_required';
    end if;
    if p_stale_seconds is null or p_stale_seconds < 60 or p_stale_seconds > 86400 then
        raise exception 'invalid_ai_job_stale_window';
    end if;

    with candidates as (
        select id
        from public.ai_jobs
        where owner_id = btrim(p_owner_id)
          and state = 'running'
          and provider_dispatch_started_at is null
          and claimed_at < now() - make_interval(secs => p_stale_seconds)
        order by claimed_at asc, id asc
        for update skip locked
        limit greatest(1, least(coalesce(p_limit, 50), 500))
    )
    update public.ai_jobs j
    set state = case when j.attempts >= j.max_attempts then 'dead' else 'queued' end,
        available_at = now(),
        claimed_at = null,
        claimed_by = null,
        last_error_code = 'stale_claim_recovered_before_dispatch',
        updated_at = now()
    from candidates c
    where j.id = c.id
      and j.owner_id = btrim(p_owner_id);

    get diagnostics reclaimed_count = row_count;
    return reclaimed_count;
end;
$$;

create or replace function public.finish_ai_job(
    p_owner_id text,
    p_id text,
    p_worker_id text,
    p_success boolean,
    p_error_code text default null,
    p_retry_after_seconds integer default 0
)
returns public.ai_jobs
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    current_job public.ai_jobs;
    next_state text;
begin
    if nullif(btrim(p_owner_id), '') is null then
        raise exception 'owner_id_required';
    end if;
    if nullif(btrim(p_id), '') is null or nullif(btrim(p_worker_id), '') is null then
        raise exception 'job_and_worker_required';
    end if;

    select * into current_job
    from public.ai_jobs
    where id = p_id
      and owner_id = btrim(p_owner_id)
    for update;

    if not found then
        raise exception 'ai_job_not_found';
    end if;
    if current_job.state <> 'running' or current_job.claimed_by <> btrim(p_worker_id) then
        raise exception 'ai_job_claim_mismatch';
    end if;

    if p_success then
        next_state := 'completed';
    elsif current_job.attempts >= current_job.max_attempts then
        next_state := 'dead';
    else
        next_state := 'queued';
    end if;

    update public.ai_jobs
    set state = next_state,
        available_at = case
            when next_state = 'queued'
                then now() + make_interval(secs => greatest(0, least(coalesce(p_retry_after_seconds, 0), 86400)))
            else available_at
        end,
        claimed_at = null,
        claimed_by = null,
        provider_dispatch_started_at = case when next_state = 'queued' then null else provider_dispatch_started_at end,
        completed_at = case when next_state = 'completed' then now() else null end,
        last_error_code = case
            when p_success then null
            else left(coalesce(nullif(btrim(p_error_code), ''), 'worker_failure'), 96)
        end,
        updated_at = now()
    where id = p_id
      and owner_id = btrim(p_owner_id)
    returning * into current_job;

    return current_job;
end;
$$;

revoke all on function public.claim_ai_jobs(text, text, integer)
    from public, anon, authenticated;
revoke all on function public.mark_ai_job_dispatched(text, text, text)
    from public, anon, authenticated;
revoke all on function public.reclaim_stale_undispatched_ai_jobs(text, integer, integer)
    from public, anon, authenticated;
revoke all on function public.finish_ai_job(text, text, text, boolean, text, integer)
    from public, anon, authenticated;

grant execute on function public.claim_ai_jobs(text, text, integer) to service_role;
grant execute on function public.mark_ai_job_dispatched(text, text, text) to service_role;
grant execute on function public.reclaim_stale_undispatched_ai_jobs(text, integer, integer) to service_role;
grant execute on function public.finish_ai_job(text, text, text, boolean, text, integer) to service_role;
