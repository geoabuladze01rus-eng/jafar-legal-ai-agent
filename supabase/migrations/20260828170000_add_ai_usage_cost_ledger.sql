create table if not exists public.ai_usage_costs (
  owner_user_id text not null,
  request_id text not null,
  user_id text not null,
  matter_id text null,
  operation text not null,
  provider text not null,
  model text not null,
  input_tokens bigint not null default 0,
  cached_input_tokens bigint not null default 0,
  output_tokens bigint not null default 0,
  cost_usd numeric(20, 8) not null,
  recorded_at timestamptz not null default now(),
  primary key (owner_user_id, request_id),
  constraint ai_usage_costs_tokens_non_negative_check
    check (
      input_tokens >= 0
      and cached_input_tokens >= 0
      and output_tokens >= 0
      and cached_input_tokens <= input_tokens
    ),
  constraint ai_usage_costs_cost_non_negative_check check (cost_usd >= 0),
  constraint ai_usage_costs_identity_check
    check (
      btrim(request_id) <> ''
      and btrim(user_id) <> ''
      and btrim(operation) <> ''
      and btrim(provider) <> ''
      and btrim(model) <> ''
    )
);

create index if not exists ai_usage_costs_owner_recorded_idx
on public.ai_usage_costs (owner_user_id, recorded_at desc);

create index if not exists ai_usage_costs_owner_user_recorded_idx
on public.ai_usage_costs (owner_user_id, user_id, recorded_at desc);

create index if not exists ai_usage_costs_owner_provider_recorded_idx
on public.ai_usage_costs (owner_user_id, provider, recorded_at desc);

alter table public.ai_usage_costs enable row level security;

-- Usage/cost accounting is a server financial-control surface. App clients must not be able
-- to insert, edit, delete, or directly enumerate records and thereby influence budget gates.
revoke all on public.ai_usage_costs from anon, authenticated;

create or replace function public.ai_spend_for_owner(
  p_owner_user_id text,
  p_user_id text,
  p_since timestamptz
)
returns numeric
language sql
stable
security definer
set search_path = public, pg_catalog
as $$
  select coalesce(sum(cost_usd), 0)::numeric
  from public.ai_usage_costs
  where owner_user_id = p_owner_user_id
    and recorded_at >= p_since
    and (p_user_id is null or user_id = p_user_id);
$$;

revoke all on function public.ai_spend_for_owner(text, text, timestamptz) from public;
revoke all on function public.ai_spend_for_owner(text, text, timestamptz) from anon;
revoke all on function public.ai_spend_for_owner(text, text, timestamptz) from authenticated;
grant execute on function public.ai_spend_for_owner(text, text, timestamptz) to service_role;
