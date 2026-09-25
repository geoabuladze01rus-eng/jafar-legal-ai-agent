create table if not exists public.telegram_publication_delivery (
  publication_id text primary key,
  payload_hash text not null,
  state text not null check (state in ('pending', 'claimed', 'sent', 'uncertain', 'failed')),
  claimed_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  telegram_message_id bigint,
  error_code text,
  reconciliation_note text,
  constraint telegram_publication_sent_requires_message_id
    check (state <> 'sent' or telegram_message_id is not null)
);

alter table public.telegram_publication_delivery enable row level security;

revoke all on table public.telegram_publication_delivery from public, anon, authenticated;

grant select, insert, update on table public.telegram_publication_delivery to service_role;

create or replace function public.claim_telegram_publication(
  p_publication_id text,
  p_payload_hash text
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_claimed boolean;
begin
  if p_publication_id is null or btrim(p_publication_id) = '' then
    raise exception 'publication_id_required';
  end if;
  if p_payload_hash is null or p_payload_hash !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid_payload_hash';
  end if;

  insert into public.telegram_publication_delivery (
    publication_id,
    payload_hash,
    state,
    claimed_at,
    updated_at
  ) values (
    p_publication_id,
    p_payload_hash,
    'claimed',
    now(),
    now()
  )
  on conflict (publication_id) do update
    set state = 'claimed',
        claimed_at = now(),
        updated_at = now(),
        error_code = null,
        reconciliation_note = null
    where public.telegram_publication_delivery.state = 'pending'
      and public.telegram_publication_delivery.payload_hash = excluded.payload_hash
  returning true into v_claimed;

  return coalesce(v_claimed, false);
end;
$$;

create or replace function public.mark_telegram_publication_sent(
  p_publication_id text,
  p_telegram_message_id bigint
)
returns void
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
begin
  update public.telegram_publication_delivery
  set state = 'sent',
      telegram_message_id = p_telegram_message_id,
      updated_at = now(),
      error_code = null
  where publication_id = p_publication_id
    and state = 'claimed';

  if not found then
    raise exception 'telegram_delivery_not_claimed';
  end if;
end;
$$;

create or replace function public.mark_telegram_publication_failed(
  p_publication_id text,
  p_error_code text
)
returns void
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
begin
  update public.telegram_publication_delivery
  set state = 'failed',
      updated_at = now(),
      error_code = left(coalesce(nullif(btrim(p_error_code), ''), 'unknown_error'), 120)
  where publication_id = p_publication_id
    and state = 'claimed';

  if not found then
    raise exception 'telegram_delivery_not_claimed';
  end if;
end;
$$;

create or replace function public.mark_telegram_publication_uncertain(
  p_publication_id text,
  p_note text
)
returns void
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
begin
  update public.telegram_publication_delivery
  set state = 'uncertain',
      updated_at = now(),
      reconciliation_note = left(coalesce(p_note, ''), 1000)
  where publication_id = p_publication_id
    and state = 'claimed';

  if not found then
    raise exception 'telegram_delivery_not_claimed';
  end if;
end;
$$;

create or replace function public.release_telegram_publication_failed(
  p_publication_id text
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_released boolean;
begin
  update public.telegram_publication_delivery
  set state = 'pending',
      updated_at = now(),
      error_code = null
  where publication_id = p_publication_id
    and state = 'failed'
  returning true into v_released;

  return coalesce(v_released, false);
end;
$$;

create or replace function public.reconcile_telegram_publication_sent(
  p_publication_id text,
  p_telegram_message_id bigint,
  p_note text
)
returns void
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
begin
  update public.telegram_publication_delivery
  set state = 'sent',
      telegram_message_id = p_telegram_message_id,
      updated_at = now(),
      reconciliation_note = left(coalesce(p_note, ''), 1000),
      error_code = null
  where publication_id = p_publication_id
    and state = 'uncertain';

  if not found then
    raise exception 'telegram_delivery_not_uncertain';
  end if;
end;
$$;

create or replace function public.get_telegram_publication_delivery(
  p_publication_id text
)
returns jsonb
language sql
stable
security definer
set search_path = public, pg_catalog
as $$
  select to_jsonb(t)
  from public.telegram_publication_delivery as t
  where t.publication_id = p_publication_id;
$$;

revoke all on function public.claim_telegram_publication(text, text) from public, anon, authenticated;
revoke all on function public.mark_telegram_publication_sent(text, bigint) from public, anon, authenticated;
revoke all on function public.mark_telegram_publication_failed(text, text) from public, anon, authenticated;
revoke all on function public.mark_telegram_publication_uncertain(text, text) from public, anon, authenticated;
revoke all on function public.release_telegram_publication_failed(text) from public, anon, authenticated;
revoke all on function public.reconcile_telegram_publication_sent(text, bigint, text) from public, anon, authenticated;
revoke all on function public.get_telegram_publication_delivery(text) from public, anon, authenticated;

grant execute on function public.claim_telegram_publication(text, text) to service_role;
grant execute on function public.mark_telegram_publication_sent(text, bigint) to service_role;
grant execute on function public.mark_telegram_publication_failed(text, text) to service_role;
grant execute on function public.mark_telegram_publication_uncertain(text, text) to service_role;
grant execute on function public.release_telegram_publication_failed(text) to service_role;
grant execute on function public.reconcile_telegram_publication_sent(text, bigint, text) to service_role;
grant execute on function public.get_telegram_publication_delivery(text) to service_role;
