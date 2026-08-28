-- Bind every executable approval to the exact payload reviewed by the lawyer.

alter table public.action_approvals
add column if not exists payload_hash text null;

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

  if old.state = 'proposed' and new.state in ('approved', 'rejected') then
    return new;
  end if;

  if old.state = 'approved' and new.state = 'executed' then
    if old.payload_hash is null or btrim(old.payload_hash) = '' then
      raise exception 'payload_binding_required';
    end if;
    return new;
  end if;

  raise exception 'invalid_action_approval_transition: % -> %', old.state, new.state;
end;
$$;

revoke all on function public.enforce_action_approval_transition() from public;
