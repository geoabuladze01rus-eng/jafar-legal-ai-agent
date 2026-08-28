-- Distributed fixed-window rate limiting for horizontally scaled API/worker instances.
-- Only opaque hashes are stored; raw user/matter identifiers and prompts are not rate-limit keys.

create table if not exists public.ai_rate_limit_buckets (
    key_hash text not null,
    bucket_start timestamptz not null,
    window_seconds integer not null,
    request_count integer not null default 0,
    updated_at timestamptz not null default now(),
    primary key (key_hash, bucket_start, window_seconds),
    constraint ai_rate_key_hash_check check (key_hash ~ '^[0-9a-f]{64}$'),
    constraint ai_rate_window_check check (window_seconds between 1 and 86400),
    constraint ai_rate_count_check check (request_count >= 0)
);

create index if not exists ai_rate_limit_cleanup_idx
    on public.ai_rate_limit_buckets (bucket_start);

alter table public.ai_rate_limit_buckets enable row level security;
revoke all on public.ai_rate_limit_buckets from anon, authenticated;
grant select, insert, update, delete on public.ai_rate_limit_buckets to service_role;

create or replace function public.consume_ai_rate_limit(
    p_key_hash text,
    p_max_requests integer,
    p_window_seconds integer
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    v_bucket_start timestamptz;
    v_count integer;
begin
    if p_key_hash is null or p_key_hash !~ '^[0-9a-f]{64}$' then
        raise exception 'invalid_rate_limit_key_hash';
    end if;
    if p_max_requests is null or p_max_requests < 1 or p_max_requests > 1000000 then
        raise exception 'invalid_rate_limit_max_requests';
    end if;
    if p_window_seconds is null or p_window_seconds < 1 or p_window_seconds > 86400 then
        raise exception 'invalid_rate_limit_window';
    end if;

    v_bucket_start := to_timestamp(
        floor(extract(epoch from clock_timestamp()) / p_window_seconds) * p_window_seconds
    );

    insert into public.ai_rate_limit_buckets (
        key_hash, bucket_start, window_seconds, request_count, updated_at
    ) values (
        p_key_hash, v_bucket_start, p_window_seconds, 1, now()
    )
    on conflict (key_hash, bucket_start, window_seconds)
    do update set
        request_count = public.ai_rate_limit_buckets.request_count + 1,
        updated_at = now()
    where public.ai_rate_limit_buckets.request_count < p_max_requests
    returning request_count into v_count;

    return v_count is not null and v_count <= p_max_requests;
end;
$$;

create or replace function public.cleanup_ai_rate_limit_buckets(
    p_retention_seconds integer default 172800
)
returns integer
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    deleted_count integer;
begin
    if p_retention_seconds is null or p_retention_seconds < 86400 or p_retention_seconds > 2592000 then
        raise exception 'invalid_rate_limit_retention';
    end if;

    delete from public.ai_rate_limit_buckets
    where bucket_start < now() - make_interval(secs => p_retention_seconds);
    get diagnostics deleted_count = row_count;
    return deleted_count;
end;
$$;

revoke all on function public.consume_ai_rate_limit(text, integer, integer)
    from public, anon, authenticated;
revoke all on function public.cleanup_ai_rate_limit_buckets(integer)
    from public, anon, authenticated;
grant execute on function public.consume_ai_rate_limit(text, integer, integer) to service_role;
grant execute on function public.cleanup_ai_rate_limit_buckets(integer) to service_role;
