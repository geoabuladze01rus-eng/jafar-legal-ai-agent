-- Editorial autopilot may generate draft material, but it must never self-certify
-- legal/factual/privacy safety or grant itself permission to publish.
--
-- This insert-only trigger is intentionally independent of the current Edge Function
-- implementation. Any new autopilot row is born in Review with an explicit blocker.
-- A later human/editorial review may update the row to Ready, but the existing
-- telegram_ready_queue_safety trigger will then require verified fact-check status,
-- low legal/privacy risk, no current-case risk, no blockers, and a valid fingerprint.

create or replace function public.enforce_editorial_autopilot_review_gate()
returns trigger
language plpgsql
set search_path = public, pg_catalog
as $$
begin
  if coalesce(new.source_notion_page_id, '') like 'autopilot:%' then
    new.status := 'Review';
    new.fact_check_status := 'pending';
    new.legal_risk := 'medium';
    new.privacy_risk := 'medium';
    new.current_case_risk := false;
    new.editorial_blockers := jsonb_build_array('autopilot_human_review_required');
  end if;

  return new;
end;
$$;

drop trigger if exists editorial_autopilot_review_gate
  on public.telegram_publication_queue;
create trigger editorial_autopilot_review_gate
before insert on public.telegram_publication_queue
for each row execute function public.enforce_editorial_autopilot_review_gate();

revoke all on function public.enforce_editorial_autopilot_review_gate()
  from public, anon, authenticated;
grant execute on function public.enforce_editorial_autopilot_review_gate()
  to service_role;
