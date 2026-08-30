-- Isolate distributed rate-limit counters by owner/tenant.
-- Opaque key hashes stay privacy-safe, but owner scope prevents one tenant's activity from
-- consuming another tenant's quota when the same logical key is used.

alter table public.ai_rate_limit_buckets
    add column if not exists owner_user_id text;

update public.ai_rate_limit_buckets
set owner_user_id = 'legacy'
where owner_user_id is null;

alter table public.ai_rate_limit_buckets
    alter column owner_user_id set not null;

alter table public.ai_rate_limit_buckets
    drop constraint if exists ai_rate_limit_buckets_pkey;

alter table public.ai_rate_limit_buckets
    add primary key (owner_user_id, key_hash, bucket_start, window_seconds);

create index if not exists ai_rate_limit_owner_cleanup_idx
    on public.ai_rate_limit_buckets (owner_user_id, bucket_start);

drop function if exists public.consume_ai_rate_limit(text, integer, integer);
drop function if exists public.cleanup_ai_rate_limit_buckets(integer);

create or replace function public.consume_ai_rate_limit(
    p_owner_user_id text,
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
    if auth.role() <> 'service_role' then
        raise exception 'service_role_required';
    end if;
    if nullif(btrim(p_owner_user_id), '') is null then
        raise exception 'owner_user_id_required';
    end if;
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
        owner_user_id, key_hash, bucket_start, window_seconds, request_count, updated_at
    ) values (
        btrim(p_owner_user_id), p_key_hash, v_bucket_start, p_window_seconds, 1, now()
    )
    on conflict (owner_user_id, key_hash, bucket_start, window_seconds)
    do update set
        request_count = public.ai_rate_limit_buckets.request_count + 1,
        updated_at = now()
    where public.ai_rate_limit_buckets.request_count < p_max_requests
    returning request_count into v_count;

    return v_count is not null and v_count <= p_max_requests;
end;
$$;

create or replace function public.cleanup_ai_rate_limit_buckets(
    p_owner_user_id text,
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
    if auth.role() <> 'service_role' then
        raise exception 'service_role_required';
    end if;
    if nullif(btrim(p_owner_user_id), '') is null then
        raise exception 'owner_user_id_required';
    end if;
    if p_retention_seconds is null or p_retention_seconds < 86400 or p_retention_seconds > 2592000 then
        raise exception 'invalid_rate_limit_retention';
    end if;

    delete from public.ai_rate_limit_buckets
    where owner_user_id = btrim(p_owner_user_id)
      and bucket_start < now() - make_interval(secs => p_retention_seconds);
    get diagnostics deleted_count = row_count;
    return deleted_count;
end;
$$;

revoke all on function public.consume_ai_rate_limit(text, text, integer, integer)
    from public, anon, authenticated;
revoke all on function public.cleanup_ai_rate_limit_buckets(text, integer)
    from public, anon, authenticated;
grant execute on function public.consume_ai_rate_limit(text, text, integer, integer) to service_role;
grant execute on function public.cleanup_ai_rate_limit_buckets(text, integer) to service_role;
