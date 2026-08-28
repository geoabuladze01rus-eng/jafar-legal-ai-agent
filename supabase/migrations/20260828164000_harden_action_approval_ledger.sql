-- Approval decisions are a privileged server-side audit ledger.
-- Apple/web clients use the FastAPI approval endpoints and must never mutate this table directly.

revoke all on table public.action_approvals from anon, authenticated;

drop policy if exists "action approvals owner can read" on public.action_approvals;
drop policy if exists "action approvals owner can insert" on public.action_approvals;
drop policy if exists "action approvals owner can update" on public.action_approvals;

create or replace function public.enforce_action_approval_transition()
returns trigger
language plpgsql
set search_path = public, pg_catalog
as $$
begin
  if new.owner_user_id is distinct from old.owner_user_id
     or new.action_id is distinct from old.action_id
     or new.action_type is distinct from old.action_type
     or new.description is distinct from old.description
     or new.requested_by is distinct from old.requested_by
     or new.requires_human_approval is distinct from old.requires_human_approval
     or new.evidence_ids is distinct from old.evidence_ids
     or new.created_at is distinct from old.created_at then
    raise exception 'immutable_action_approval_fields';
  end if;

  if old.state = 'proposed' and new.state in ('approved', 'rejected') then
    return new;
  end if;

  if old.state = 'approved' and new.state = 'executed' then
    return new;
  end if;

  raise exception 'invalid_action_approval_transition: % -> %', old.state, new.state;
end;
$$;

drop trigger if exists trg_enforce_action_approval_transition on public.action_approvals;
create trigger trg_enforce_action_approval_transition
before update on public.action_approvals
for each row execute function public.enforce_action_approval_transition();

revoke all on function public.enforce_action_approval_transition() from public;
