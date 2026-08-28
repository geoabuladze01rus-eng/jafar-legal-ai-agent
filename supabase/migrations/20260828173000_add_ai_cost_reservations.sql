-- Reserve estimated AI spend before dispatch so concurrent workers cannot oversubscribe a budget.

create table if not exists public.ai_cost_reservations (
  owner_user_id text not null,
  reservation_id text not null,
  user_id text not null,
  matter_id text null,
  operation text not null,
  estimated_cost_usd numeric(18,8) not null check (estimated_cost_usd >= 0),
  state text not null default 'active' check (state in ('active', 'released', 'settled', 'expired')),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  closed_at timestamptz null,
  primary key (owner_user_id, reservation_id),
  check (expires_at > created_at)
);

create index if not exists ai_cost_reservations_owner_state_expiry_idx
  on public.ai_cost_reservations (owner_user_id, state, expires_at);
create index if not exists ai_cost_reservations_owner_user_state_idx
  on public.ai_cost_reservations (owner_user_id, user_id, state, created_at);

alter table public.ai_cost_reservations enable row level security;
revoke all on public.ai_cost_reservations from anon, authenticated;

create or replace function public.reserve_ai_cost_for_owner(
  p_owner_user_id text,
  p_reservation_id text,
  p_user_id text,
  p_matter_id text,
  p_operation text,
  p_estimated_cost_usd numeric,
  p_expires_at timestamptz,
  p_user_daily_limit_usd numeric default null,
  p_user_monthly_limit_usd numeric default null,
  p_global_daily_limit_usd numeric default null
)
returns public.ai_cost_reservations
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_now timestamptz := now();
  v_day timestamptz := date_trunc('day', v_now);
  v_month timestamptz := date_trunc('month', v_now);
  v_user_day numeric := 0;
  v_user_month numeric := 0;
  v_global_day numeric := 0;
  v_reserved_user_day numeric := 0;
  v_reserved_user_month numeric := 0;
  v_reserved_global_day numeric := 0;
  v_row public.ai_cost_reservations;
begin
  if auth.role() <> 'service_role' then
    raise exception 'service_role_required';
  end if;
  if coalesce(btrim(p_owner_user_id), '') = ''
     or coalesce(btrim(p_reservation_id), '') = ''
     or coalesce(btrim(p_user_id), '') = ''
     or coalesce(btrim(p_operation), '') = '' then
    raise exception 'reservation_identity_required';
  end if;
  if p_estimated_cost_usd < 0 or p_expires_at <= v_now then
    raise exception 'invalid_reservation';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(p_owner_user_id, 0));

  update public.ai_cost_reservations
     set state = 'expired', closed_at = v_now
   where owner_user_id = p_owner_user_id
     and state = 'active'
     and expires_at <= v_now;

  select coalesce(sum(cost_usd), 0) into v_user_day
    from public.ai_usage_costs
   where owner_user_id = p_owner_user_id and user_id = p_user_id and recorded_at >= v_day;
  select coalesce(sum(cost_usd), 0) into v_user_month
    from public.ai_usage_costs
   where owner_user_id = p_owner_user_id and user_id = p_user_id and recorded_at >= v_month;
  select coalesce(sum(cost_usd), 0) into v_global_day
    from public.ai_usage_costs
   where owner_user_id = p_owner_user_id and recorded_at >= v_day;

  select coalesce(sum(estimated_cost_usd), 0) into v_reserved_user_day
    from public.ai_cost_reservations
   where owner_user_id = p_owner_user_id and user_id = p_user_id
     and state = 'active' and created_at >= v_day;
  select coalesce(sum(estimated_cost_usd), 0) into v_reserved_user_month
    from public.ai_cost_reservations
   where owner_user_id = p_owner_user_id and user_id = p_user_id
     and state = 'active' and created_at >= v_month;
  select coalesce(sum(estimated_cost_usd), 0) into v_reserved_global_day
    from public.ai_cost_reservations
   where owner_user_id = p_owner_user_id and state = 'active' and created_at >= v_day;

  if p_user_daily_limit_usd is not null
     and v_user_day + v_reserved_user_day + p_estimated_cost_usd > p_user_daily_limit_usd then
    raise exception 'cost_budget_exceeded:user_daily';
  end if;
  if p_user_monthly_limit_usd is not null
     and v_user_month + v_reserved_user_month + p_estimated_cost_usd > p_user_monthly_limit_usd then
    raise exception 'cost_budget_exceeded:user_monthly';
  end if;
  if p_global_daily_limit_usd is not null
     and v_global_day + v_reserved_global_day + p_estimated_cost_usd > p_global_daily_limit_usd then
    raise exception 'cost_budget_exceeded:global_daily';
  end if;

  insert into public.ai_cost_reservations (
    owner_user_id, reservation_id, user_id, matter_id, operation,
    estimated_cost_usd, expires_at
  ) values (
    p_owner_user_id, p_reservation_id, p_user_id, nullif(p_matter_id, ''), p_operation,
    p_estimated_cost_usd, p_expires_at
  ) returning * into v_row;
  return v_row;
end;
$$;

create or replace function public.close_ai_cost_reservation_for_owner(
  p_owner_user_id text,
  p_reservation_id text,
  p_state text
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
begin
  if auth.role() <> 'service_role' then
    raise exception 'service_role_required';
  end if;
  if p_state not in ('released', 'settled') then
    raise exception 'invalid_reservation_close_state';
  end if;
  update public.ai_cost_reservations
     set state = p_state, closed_at = now()
   where owner_user_id = p_owner_user_id
     and reservation_id = p_reservation_id
     and state = 'active';
  return found;
end;
$$;

revoke all on function public.reserve_ai_cost_for_owner(
  text, text, text, text, text, numeric, timestamptz, numeric, numeric, numeric
) from public, anon, authenticated;
revoke all on function public.close_ai_cost_reservation_for_owner(text, text, text)
  from public, anon, authenticated;
grant execute on function public.reserve_ai_cost_for_owner(
  text, text, text, text, text, numeric, timestamptz, numeric, numeric, numeric
) to service_role;
grant execute on function public.close_ai_cost_reservation_for_owner(text, text, text)
  to service_role;
