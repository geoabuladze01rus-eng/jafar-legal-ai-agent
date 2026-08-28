-- Reconcile ambiguous executing actions atomically with the append-only evidence ledger.

create or replace function public.reconcile_action_for_owner(
  p_owner_user_id uuid,
  p_action_id text,
  p_decision text,
  p_operator_id text,
  p_evidence_note text
)
returns public.action_approvals
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_action public.action_approvals;
  v_audit_reason text;
begin
  if p_owner_user_id is null then
    raise exception 'owner_user_id_required';
  end if;
  if p_action_id is null or btrim(p_action_id) = '' then
    raise exception 'action_id_required';
  end if;
  if char_length(btrim(p_action_id)) > 200 then
    raise exception 'action_id_too_long';
  end if;
  if p_operator_id is null or btrim(p_operator_id) = '' then
    raise exception 'operator_id_required';
  end if;
  if char_length(btrim(p_operator_id)) > 200 then
    raise exception 'operator_id_too_long';
  end if;
  if p_evidence_note is null or btrim(p_evidence_note) = '' then
    raise exception 'reconciliation_evidence_note_required';
  end if;
  if char_length(btrim(p_evidence_note)) > 4000 then
    raise exception 'reconciliation_evidence_note_too_long';
  end if;
  if p_decision not in ('confirmed_not_executed', 'confirmed_executed') then
    raise exception 'unsupported_reconciliation_decision';
  end if;

  select * into v_action
  from public.action_approvals
  where owner_user_id = p_owner_user_id
    and action_id = btrim(p_action_id)
  for update;

  if not found then
    raise exception 'action_not_found';
  end if;
  if v_action.state <> 'executing' then
    raise exception 'action_not_executing';
  end if;
  if v_action.execution_claimed_by is null or btrim(v_action.execution_claimed_by) = '' then
    raise exception 'execution_claim_owner_missing';
  end if;

  v_audit_reason := 'reconciliation by ' || btrim(p_operator_id) || ': ' || btrim(p_evidence_note);

  if p_decision = 'confirmed_not_executed' then
    update public.action_approvals
    set state = 'approved',
        execution_claimed_at = null,
        execution_claimed_by = null,
        execution_error = v_audit_reason
    where owner_user_id = p_owner_user_id
      and action_id = btrim(p_action_id)
      and state = 'executing'
    returning * into v_action;
  else
    update public.action_approvals
    set state = 'executed',
        executed_at = now(),
        execution_error = null
    where owner_user_id = p_owner_user_id
      and action_id = btrim(p_action_id)
      and state = 'executing'
    returning * into v_action;
  end if;

  if not found then
    raise exception 'reconciliation_transition_conflict';
  end if;

  insert into public.action_reconciliation_audit (
    owner_user_id,
    action_id,
    decision,
    operator_id,
    evidence_note,
    recorded_at
  ) values (
    p_owner_user_id,
    btrim(p_action_id),
    p_decision,
    btrim(p_operator_id),
    btrim(p_evidence_note),
    now()
  );

  return v_action;
end;
$$;

revoke all on function public.reconcile_action_for_owner(uuid, text, text, text, text)
from public, anon, authenticated;
grant execute on function public.reconcile_action_for_owner(uuid, text, text, text, text)
to service_role;
