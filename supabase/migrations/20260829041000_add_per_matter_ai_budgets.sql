-- Add durable per-matter AI spend accounting and reservation ceilings.

create index if not exists ai_usage_costs_owner_matter_recorded_idx
  on public.ai_usage_costs (owner_user_id, matter_id, recorded_at desc)
  where matter_id is not null;

create or replace function public.ai_spend_for_matter_for_owner(
  p_owner_user_id text,
  p_matter_id text,
  p_since timestamptz
)
returns numeric
language plpgsql
stable
security definer
set search_path = public, pg_catalog
as $$
begin
  if auth.role() <> 'service_role' then
    raise exception 'service_role_required';
  end if;
  if coalesce(btrim(p_owner_user_id), '') = ''
     or coalesce(btrim(p_matter_id), '') = '' then
    raise exception 'matter_spend_identity_required';
  end if;
  if p_since is null then
    raise exception 'matter_spend_since_required';
  end if;

  return (
    select coalesce(sum(cost_usd), 0)::numeric
    from public.ai_usage_costs
    where owner_user_id = p_owner_user_id
      and matter_id = p_matter_id
      and recorded_at >= p_since
  );
end;
$$;

revoke all on function public.ai_spend_for_matter_for_owner(text, text, timestamptz)
  from public, anon, authenticated;
grant execute on function public.ai_spend_for_matter_for_owner(text, text, timestamptz)
  to service_role;

-- Replace the previous reservation RPC signature with a matter-aware one. This keeps all
-- budget checks under the same owner advisory lock, preventing concurrent workers from
-- oversubscribing user, matter, or global ceilings.
drop function if exists public.reserve_ai_cost_for_owner(
  text, text, text, text, text, numeric, timestamptz, numeric, numeric, numeric
);

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
  p_matter_daily_limit_usd numeric default null,
  p_matter_monthly_limit_usd numeric default null,
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
  v_matter_day numeric := 0;
  v_matter_month numeric := 0;
  v_global_day numeric := 0;
  v_reserved_user_day numeric := 0;
  v_reserved_user_month numeric := 0;
  v_reserved_matter_day numeric := 0;
  v_reserved_matter_month numeric := 0;
  v_reserved_global_day numeric := 0;
  v_row public.ai_cost_reservations;
  v_matter_id text := nullif(btrim(coalesce(p_matter_id, '')), '');
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
  if (p_matter_daily_limit_usd is not null or p_matter_monthly_limit_usd is not null)
     and v_matter_id is null then
    -- Requests not attached to a matter remain governed by request/user/global ceilings.
    null;
  end if;

  perform pg_advisory_xact_lock(hashtextextended(p_owner_user_id, 0));

  update public.ai_cost_reservations
     set state = 'expired', closed_at = v_now
   where owner_user_id = p_owner_user_id
     and state = 'active'
     and expires_at <= v_now;

  select coalesce(sum(cost_usd), 0) into v_user_day
    from public.ai_usage_costs
   where owner_user_id = p_owner_user_id
     and user_id = p_user_id
     and recorded_at >= v_day;

  select coalesce(sum(cost_usd), 0) into v_user_month
    from public.ai_usage_costs
   where owner_user_id = p_owner_user_id
     and user_id = p_user_id
     and recorded_at >= v_month;

  if v_matter_id is not null then
    select coalesce(sum(cost_usd), 0) into v_matter_day
      from public.ai_usage_costs
     where owner_user_id = p_owner_user_id
       and matter_id = v_matter_id
       and recorded_at >= v_day;

    select coalesce(sum(cost_usd), 0) into v_matter_month
      from public.ai_usage_costs
     where owner_user_id = p_owner_user_id
       and matter_id = v_matter_id
       and recorded_at >= v_month;
  end if;

  select coalesce(sum(cost_usd), 0) into v_global_day
    from public.ai_usage_costs
   where owner_user_id = p_owner_user_id
     and recorded_at >= v_day;

  select coalesce(sum(estimated_cost_usd), 0) into v_reserved_user_day
    from public.ai_cost_reservations
   where owner_user_id = p_owner_user_id
     and user_id = p_user_id
     and state = 'active'
     and created_at >= v_day;

  select coalesce(sum(estimated_cost_usd), 0) into v_reserved_user_month
    from public.ai_cost_reservations
   where owner_user_id = p_owner_user_id
     and user_id = p_user_id
     and state = 'active'
     and created_at >= v_month;

  if v_matter_id is not null then
    select coalesce(sum(estimated_cost_usd), 0) into v_reserved_matter_day
      from public.ai_cost_reservations
     where owner_user_id = p_owner_user_id
       and matter_id = v_matter_id
       and state = 'active'
       and created_at >= v_day;

    select coalesce(sum(estimated_cost_usd), 0) into v_reserved_matter_month
      from public.ai_cost_reservations
     where owner_user_id = p_owner_user_id
       and matter_id = v_matter_id
       and state = 'active'
       and created_at >= v_month;
  end if;

  select coalesce(sum(estimated_cost_usd), 0) into v_reserved_global_day
    from public.ai_cost_reservations
   where owner_user_id = p_owner_user_id
     and state = 'active'
     and created_at >= v_day;

  if p_user_daily_limit_usd is not null
     and v_user_day + v_reserved_user_day + p_estimated_cost_usd > p_user_daily_limit_usd then
    raise exception 'cost_budget_exceeded:user_daily';
  end if;
  if p_user_monthly_limit_usd is not null
     and v_user_month + v_reserved_user_month + p_estimated_cost_usd > p_user_monthly_limit_usd then
    raise exception 'cost_budget_exceeded:user_monthly';
  end if;
  if v_matter_id is not null
     and p_matter_daily_limit_usd is not null
     and v_matter_day + v_reserved_matter_day + p_estimated_cost_usd > p_matter_daily_limit_usd then
    raise exception 'cost_budget_exceeded:matter_daily';
  end if;
  if v_matter_id is not null
     and p_matter_monthly_limit_usd is not null
     and v_matter_month + v_reserved_matter_month + p_estimated_cost_usd > p_matter_monthly_limit_usd then
    raise exception 'cost_budget_exceeded:matter_monthly';
  end if;
  if p_global_daily_limit_usd is not null
     and v_global_day + v_reserved_global_day + p_estimated_cost_usd > p_global_daily_limit_usd then
    raise exception 'cost_budget_exceeded:global_daily';
  end if;

  insert into public.ai_cost_reservations (
    owner_user_id,
    reservation_id,
    user_id,
    matter_id,
    operation,
    estimated_cost_usd,
    expires_at
  ) values (
    p_owner_user_id,
    p_reservation_id,
    p_user_id,
    v_matter_id,
    p_operation,
    p_estimated_cost_usd,
    p_expires_at
  ) returning * into v_row;

  return v_row;
end;
$$;

revoke all on function public.reserve_ai_cost_for_owner(
  text, text, text, text, text, numeric, timestamptz,
  numeric, numeric, numeric, numeric, numeric
) from public, anon, authenticated;
grant execute on function public.reserve_ai_cost_for_owner(
  text, text, text, text, text, numeric, timestamptz,
  numeric, numeric, numeric, numeric, numeric
) to service_role;
