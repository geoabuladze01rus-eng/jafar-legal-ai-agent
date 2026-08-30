-- Prevent duplicate externally visible actions across concurrent workers.
-- An approved action must be atomically claimed before the side-effect handler is invoked.

alter table public.action_approvals
  add column if not exists execution_claimed_at timestamptz null,
  add column if not exists execution_claimed_by text null,
  add column if not exists execution_error text null;

alter table public.action_approvals
  drop constraint if exists action_approvals_state_check,
  drop constraint if exists action_approvals_decision_consistency_check;

alter table public.action_approvals
  add constraint action_approvals_state_check
    check (state in ('proposed', 'approved', 'rejected', 'executing', 'executed')),
  add constraint action_approvals_decision_consistency_check
    check (
      (state = 'proposed'
        and decided_at is null and decided_by is null
        and execution_claimed_at is null and execution_claimed_by is null
        and executed_at is null)
      or
      (state = 'approved'
        and decided_at is not null and decided_by is not null
        and payload_hash is not null and btrim(payload_hash) <> ''
        and execution_claimed_at is null and execution_claimed_by is null
        and executed_at is null)
      or
      (state = 'rejected'
        and decided_at is not null and decided_by is not null
        and decision_reason is not null and btrim(decision_reason) <> ''
        and execution_claimed_at is null and execution_claimed_by is null
        and executed_at is null)
      or
      (state = 'executing'
        and decided_at is not null and decided_by is not null
        and payload_hash is not null and btrim(payload_hash) <> ''
        and execution_claimed_at is not null
        and execution_claimed_by is not null and btrim(execution_claimed_by) <> ''
        and executed_at is null)
      or
      (state = 'executed'
        and decided_at is not null and decided_by is not null
        and payload_hash is not null and btrim(payload_hash) <> ''
        and execution_claimed_at is not null
        and execution_claimed_by is not null and btrim(execution_claimed_by) <> ''
        and executed_at is not null)
    );

create index if not exists action_approvals_owner_executing_idx
on public.action_approvals (owner_user_id, execution_claimed_at)
where state = 'executing';

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
     or new.payload_hash is distinct from old.payload_hash
     or new.created_at is distinct from old.created_at then
    raise exception 'immutable_action_approval_fields';
  end if;

  if old.state <> 'proposed' and (
       new.decided_at is distinct from old.decided_at
       or new.decided_by is distinct from old.decided_by
       or new.decision_reason is distinct from old.decision_reason
     ) then
    raise exception 'immutable_action_approval_decision';
  end if;

  if old.state = 'proposed' and new.state in ('approved', 'rejected') then
    return new;
  end if;

  if old.state = 'approved' and new.state = 'executing' then
    if new.execution_claimed_at is null
       or new.execution_claimed_by is null
       or btrim(new.execution_claimed_by) = '' then
      raise exception 'execution_claim_required';
    end if;
    return new;
  end if;

  if old.state = 'executing' and new.state = 'approved' then
    if new.execution_claimed_at is not null or new.execution_claimed_by is not null then
      raise exception 'execution_claim_must_be_cleared_for_retry';
    end if;
    if new.execution_error is null or btrim(new.execution_error) = '' then
      raise exception 'execution_error_required_for_retry';
    end if;
    return new;
  end if;

  if old.state = 'executing' and new.state = 'executed' then
    if new.executed_at is null then
      raise exception 'executed_at_required';
    end if;
    return new;
  end if;

  raise exception 'invalid_action_approval_transition: % -> %', old.state, new.state;
end;
$$;

revoke all on function public.enforce_action_approval_transition() from public;
