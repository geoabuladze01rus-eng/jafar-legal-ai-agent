create table if not exists public.action_approvals (
  owner_user_id text not null,
  action_id text not null,
  action_type text not null,
  description text not null,
  requested_by text not null default 'jafar',
  state text not null default 'proposed',
  requires_human_approval boolean not null default true,
  evidence_ids jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  decided_at timestamptz null,
  decided_by text null,
  decision_reason text null,
  executed_at timestamptz null,
  primary key (owner_user_id, action_id),
  constraint action_approvals_state_check
    check (state in ('proposed', 'approved', 'rejected', 'executed')),
  constraint action_approvals_evidence_array_check
    check (jsonb_typeof(evidence_ids) = 'array'),
  constraint action_approvals_decision_consistency_check
    check (
      (state = 'proposed' and decided_at is null and decided_by is null and executed_at is null)
      or
      (state = 'approved' and decided_at is not null and decided_by is not null and executed_at is null)
      or
      (state = 'rejected' and decided_at is not null and decided_by is not null
        and decision_reason is not null and btrim(decision_reason) <> '' and executed_at is null)
      or
      (state = 'executed' and decided_at is not null and decided_by is not null
        and executed_at is not null)
    )
);

create index if not exists action_approvals_owner_state_created_idx
on public.action_approvals (owner_user_id, state, created_at);

alter table public.action_approvals enable row level security;

create policy "action approvals owner can read" on public.action_approvals
for select to authenticated
using (owner_user_id = (select auth.uid())::text);

create policy "action approvals owner can insert" on public.action_approvals
for insert to authenticated
with check (owner_user_id = (select auth.uid())::text);

create policy "action approvals owner can update" on public.action_approvals
for update to authenticated
using (owner_user_id = (select auth.uid())::text)
with check (owner_user_id = (select auth.uid())::text);

revoke delete on public.action_approvals from anon, authenticated;
