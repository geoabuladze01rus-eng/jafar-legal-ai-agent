-- Approved Telegram visual assets for fail-closed photo publication.
--
-- The table stores only operator-approved, versioned assets. Publication rows refer
-- to an immutable asset_key (for example `what_to_do:v1`). The production worker
-- must resolve the key + category through resolve_telegram_visual_asset before it
-- can construct a Telegram SendPhoto binary payload.
--
-- This migration is intentionally idempotent enough to reconcile environments
-- where the table/functions were created operationally before being committed to
-- source control. It does not seed or activate any visual asset.

create table if not exists public.telegram_visual_assets (
    asset_key text primary key,
    category text not null,
    version integer not null default 1,
    filename text not null,
    mime_type text not null,
    sha256 text not null,
    data_base64 text not null,
    approved boolean not null default false,
    active boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Existing production data already satisfies these constraints. Keep the checks
-- explicit so a malformed binary cannot later masquerade as an approved asset.
do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'telegram_visual_assets_version_check'
          and conrelid = 'public.telegram_visual_assets'::regclass
    ) then
        alter table public.telegram_visual_assets
            add constraint telegram_visual_assets_version_check check (version > 0);
    end if;

    if not exists (
        select 1
        from pg_constraint
        where conname = 'telegram_visual_assets_sha256_check'
          and conrelid = 'public.telegram_visual_assets'::regclass
    ) then
        alter table public.telegram_visual_assets
            add constraint telegram_visual_assets_sha256_check
            check (sha256 ~ '^[0-9a-f]{64}$');
    end if;
end
$$;

alter table public.telegram_visual_assets enable row level security;

-- No public RLS policy is created. Direct table access is service-role only.
revoke all on table public.telegram_visual_assets from public;
revoke all on table public.telegram_visual_assets from anon;
revoke all on table public.telegram_visual_assets from authenticated;
grant select, insert, update, delete on table public.telegram_visual_assets to service_role;

create or replace function public.touch_telegram_visual_assets_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists telegram_visual_assets_touch_updated_at
    on public.telegram_visual_assets;
create trigger telegram_visual_assets_touch_updated_at
before update on public.telegram_visual_assets
for each row
execute function public.touch_telegram_visual_assets_updated_at();

-- Legacy read RPC retained for compatibility. New publication code should use the
-- category-aware resolver below.
create or replace function public.get_telegram_visual_asset(p_asset_key text)
returns table (
    asset_key text,
    category text,
    version integer,
    filename text,
    mime_type text,
    sha256 text,
    data_base64 text
)
language sql
stable
security definer
set search_path = public
as $$
    select
        a.asset_key,
        a.category,
        a.version,
        a.filename,
        a.mime_type,
        a.sha256,
        a.data_base64
    from public.telegram_visual_assets a
    where a.asset_key = p_asset_key
      and a.approved is true
      and a.active is true
      and coalesce(a.data_base64, '') <> ''
    limit 1;
$$;

create or replace function public.resolve_telegram_visual_asset(
    p_asset_key text,
    p_category text
)
returns table (
    asset_key text,
    category text,
    version integer,
    filename text,
    mime_type text,
    sha256 text,
    data_base64 text
)
language plpgsql
security definer
set search_path = public
as $$
begin
    if coalesce(btrim(p_asset_key), '') = '' then
        raise exception 'visual_asset_key_required' using errcode = 'P0001';
    end if;

    if coalesce(btrim(p_category), '') = '' then
        raise exception 'visual_category_required' using errcode = 'P0001';
    end if;

    return query
    select
        v.asset_key,
        v.category,
        v.version,
        v.filename,
        v.mime_type,
        v.sha256,
        v.data_base64
    from public.telegram_visual_assets v
    where v.asset_key = p_asset_key
      and v.category = p_category
      and v.approved is true
      and v.active is true
      and coalesce(v.data_base64, '') <> ''
      and v.sha256 ~ '^[0-9a-f]{64}$'
    limit 1;

    if not found then
        raise exception 'approved_visual_asset_not_found' using errcode = 'P0001';
    end if;
end;
$$;

-- SECURITY DEFINER RPCs are deliberately not executable by public client roles.
revoke all on function public.get_telegram_visual_asset(text) from public;
revoke all on function public.get_telegram_visual_asset(text) from anon;
revoke all on function public.get_telegram_visual_asset(text) from authenticated;
grant execute on function public.get_telegram_visual_asset(text) to service_role;

revoke all on function public.resolve_telegram_visual_asset(text, text) from public;
revoke all on function public.resolve_telegram_visual_asset(text, text) from anon;
revoke all on function public.resolve_telegram_visual_asset(text, text) from authenticated;
grant execute on function public.resolve_telegram_visual_asset(text, text) to service_role;

-- Trigger functions do not need to be callable by public API roles.
revoke all on function public.touch_telegram_visual_assets_updated_at() from public;
revoke all on function public.touch_telegram_visual_assets_updated_at() from anon;
revoke all on function public.touch_telegram_visual_assets_updated_at() from authenticated;
grant execute on function public.touch_telegram_visual_assets_updated_at() to service_role;

comment on table public.telegram_visual_assets is
    'Operator-approved versioned binary assets for Telegram photo publication.';
comment on function public.resolve_telegram_visual_asset(text, text) is
    'Fail-closed resolver for approved active Telegram visual assets by key and category.';
