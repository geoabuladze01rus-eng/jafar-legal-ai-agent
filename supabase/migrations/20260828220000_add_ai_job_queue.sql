-- Durable server-only queue for expensive AI work.
-- Clients must never be able to enumerate prompts/payloads or mutate worker state.

create table if not exists public.ai_jobs (
    id text primary key,
    owner_id text not null,
    operation text not null,
    payload jsonb not null default '{}'::jsonb,
    priority integer not null default 100,
    state text not null default 'queued',
    attempts integer not null default 0,
    max_attempts integer not null default 3,
    available_at timestamptz not null default now(),
    claimed_at timestamptz,
    claimed_by text,
    completed_at timestamptz,
    last_error_code text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint ai_jobs_state_check
        check (state in ('queued', 'running', 'completed', 'failed', 'dead')),
    constraint ai_jobs_attempts_check
        check (attempts >= 0 and max_attempts between 1 and 20 and attempts <= max_attempts),
    constraint ai_jobs_claim_shape_check
        check (
            (state = 'running' and claimed_at is not null and nullif(btrim(claimed_by), '') is not null)
            or
            (state <> 'running')
        )
);

create index if not exists ai_jobs_claim_idx
    on public.ai_jobs (state, available_at, priority, created_at)
    where state = 'queued';

create index if not exists ai_jobs_owner_state_idx
    on public.ai_jobs (owner_id, state, created_at desc);

alter table public.ai_jobs enable row level security;
revoke all on public.ai_jobs from anon, authenticated;
grant select, insert, update, delete on public.ai_jobs to service_role;

create or replace function public.claim_ai_jobs(
    p_worker_id text,
    p_limit integer default 5
)
returns setof public.ai_jobs
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
    if nullif(btrim(p_worker_id), '') is null then
        raise exception 'worker_id_required';
    end if;

    return query
    with candidates as (
        select j.id
        from public.ai_jobs j
        where j.state = 'queued'
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
        returning j.*
    )
    select * from claimed;
end;
$$;

create or replace function public.finish_ai_job(
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
    if nullif(btrim(p_id), '') is null or nullif(btrim(p_worker_id), '') is null then
        raise exception 'job_and_worker_required';
    end if;

    select * into current_job
    from public.ai_jobs
    where id = p_id
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
        completed_at = case when next_state = 'completed' then now() else null end,
        last_error_code = case
            when p_success then null
            else left(coalesce(nullif(btrim(p_error_code), ''), 'worker_failure'), 96)
        end,
        updated_at = now()
    where id = p_id
    returning * into current_job;

    return current_job;
end;
$$;

revoke all on function public.claim_ai_jobs(text, integer) from public, anon, authenticated;
revoke all on function public.finish_ai_job(text, text, boolean, text, integer) from public, anon, authenticated;
grant execute on function public.claim_ai_jobs(text, integer) to service_role;
grant execute on function public.finish_ai_job(text, text, boolean, text, integer) to service_role;
