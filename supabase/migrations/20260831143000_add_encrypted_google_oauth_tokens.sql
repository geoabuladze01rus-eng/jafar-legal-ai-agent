create extension if not exists pgcrypto;

create table if not exists public.google_oauth_tokens (
    subject text primary key,
    access_token_encrypted bytea not null,
    refresh_token_encrypted bytea,
    expires_at timestamptz not null,
    scope text,
    token_type text not null default 'Bearer',
    updated_at timestamptz not null default now()
);

alter table public.google_oauth_tokens enable row level security;
revoke all on table public.google_oauth_tokens from anon, authenticated;
grant select, insert, update, delete on table public.google_oauth_tokens to service_role;

create or replace function public.upsert_google_oauth_token(
    p_subject text,
    p_access_token text,
    p_refresh_token text,
    p_expires_at timestamptz,
    p_scope text,
    p_token_type text,
    p_encryption_key text
) returns void
language plpgsql
security definer
set search_path = public, extensions
as $$
begin
    insert into public.google_oauth_tokens (
        subject, access_token_encrypted, refresh_token_encrypted,
        expires_at, scope, token_type, updated_at
    ) values (
        p_subject,
        pgp_sym_encrypt(p_access_token, p_encryption_key),
        case when p_refresh_token is null or p_refresh_token = '' then null else pgp_sym_encrypt(p_refresh_token, p_encryption_key) end,
        p_expires_at,
        p_scope,
        coalesce(nullif(p_token_type, ''), 'Bearer'),
        now()
    )
    on conflict (subject) do update set
        access_token_encrypted = excluded.access_token_encrypted,
        refresh_token_encrypted = coalesce(excluded.refresh_token_encrypted, public.google_oauth_tokens.refresh_token_encrypted),
        expires_at = excluded.expires_at,
        scope = excluded.scope,
        token_type = excluded.token_type,
        updated_at = now();
end;
$$;

create or replace function public.load_google_oauth_token(
    p_subject text,
    p_encryption_key text
) returns table (
    access_token text,
    refresh_token text,
    expires_at timestamptz,
    scope text,
    token_type text
)
language sql
security definer
set search_path = public, extensions
as $$
    select
        pgp_sym_decrypt(access_token_encrypted, p_encryption_key),
        case when refresh_token_encrypted is null then null else pgp_sym_decrypt(refresh_token_encrypted, p_encryption_key) end,
        t.expires_at,
        t.scope,
        t.token_type
    from public.google_oauth_tokens t
    where t.subject = p_subject;
$$;

revoke all on function public.upsert_google_oauth_token(text,text,text,timestamptz,text,text,text) from public, anon, authenticated;
revoke all on function public.load_google_oauth_token(text,text) from public, anon, authenticated;
grant execute on function public.upsert_google_oauth_token(text,text,text,timestamptz,text,text,text) to service_role;
grant execute on function public.load_google_oauth_token(text,text) to service_role;
