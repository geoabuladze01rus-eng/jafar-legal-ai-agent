-- Durable append-only evidence trail for manual recovery of ambiguous external side effects.

create table if not exists public.action_reconciliation_audit (
  id bigint generated always as identity primary key,
  owner_user_id uuid not null,
  action_id text not null,
  decision text not null check (decision in ('confirmed_not_executed', 'confirmed_executed')),
  operator_id text not null check (btrim(operator_id) <> ''),
  evidence_note text not null check (btrim(evidence_note) <> ''),
  recorded_at timestamptz not null default now()
);

create index if not exists action_reconciliation_audit_owner_action_idx
on public.action_reconciliation_audit (owner_user_id, action_id, recorded_at);

alter table public.action_reconciliation_audit enable row level security;

revoke all on table public.action_reconciliation_audit from public, anon, authenticated;
grant select, insert on table public.action_reconciliation_audit to service_role;
grant usage, select on sequence public.action_reconciliation_audit_id_seq to service_role;

create or replace function public.prevent_action_reconciliation_audit_mutation()
returns trigger
language plpgsql
set search_path = public, pg_catalog
as $$
begin
  raise exception 'action_reconciliation_audit_is_append_only';
end;
$$;

revoke all on function public.prevent_action_reconciliation_audit_mutation() from public;

drop trigger if exists action_reconciliation_audit_no_update on public.action_reconciliation_audit;
create trigger action_reconciliation_audit_no_update
before update on public.action_reconciliation_audit
for each row execute function public.prevent_action_reconciliation_audit_mutation();

drop trigger if exists action_reconciliation_audit_no_delete on public.action_reconciliation_audit;
create trigger action_reconciliation_audit_no_delete
before delete on public.action_reconciliation_audit
for each row execute function public.prevent_action_reconciliation_audit_mutation();
