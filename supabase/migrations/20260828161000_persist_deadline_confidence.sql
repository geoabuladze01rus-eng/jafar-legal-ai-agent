alter table public.deadlines
add column if not exists confidence double precision not null default 0.0;

alter table public.deadlines
drop constraint if exists deadlines_confidence_range;

alter table public.deadlines
add constraint deadlines_confidence_range
check (confidence >= 0.0 and confidence <= 1.0);

create or replace function public.record_document_event(
  p_matter_id uuid,
  p_title text,
  p_event_date timestamptz,
  p_description text default null,
  p_source_document text default null,
  p_document_fingerprint text default null,
  p_deadlines jsonb default '[]'::jsonb
)
returns public.matter_events
language plpgsql
security invoker
set search_path = public, pg_catalog
as $$
declare
  v_event public.matter_events;
  v_owner text;
  v_deadline jsonb;
  v_confidence double precision;
begin
  select owner_user_id into v_owner
  from public.matters
  where id = p_matter_id
    and owner_user_id = (select auth.uid())::text
  for update;

  if v_owner is null then
    raise exception 'matter_not_found_or_forbidden';
  end if;

  if p_document_fingerprint is not null then
    select * into v_event from public.matter_events
    where matter_id = p_matter_id and document_fingerprint = p_document_fingerprint;
    if found then return v_event; end if;
  end if;

  for v_deadline in
    select * from jsonb_array_elements(coalesce(p_deadlines, '[]'::jsonb))
  loop
    v_confidence := coalesce((v_deadline->>'confidence')::double precision, 0.0);
    if v_confidence < 0.0 or v_confidence > 1.0 then
      raise exception 'deadline_confidence_out_of_range';
    end if;

    insert into public.deadlines
      (matter_id, owner_user_id, title, due_date, source_text, confidence)
    values
      (
        p_matter_id,
        v_owner,
        v_deadline->>'title',
        (v_deadline->>'due_date')::timestamptz,
        v_deadline->>'source_text',
        v_confidence
      );
  end loop;

  insert into public.matter_events
    (
      matter_id,
      owner_user_id,
      title,
      event_date,
      description,
      source_document,
      document_fingerprint
    )
  values
    (
      p_matter_id,
      v_owner,
      p_title,
      p_event_date,
      p_description,
      p_source_document,
      p_document_fingerprint
    )
  returning * into v_event;

  update public.matters
  set updated_at = now()
  where id = p_matter_id;

  return v_event;
exception
  when unique_violation then
    if p_document_fingerprint is not null then
      select * into v_event from public.matter_events
      where matter_id = p_matter_id and document_fingerprint = p_document_fingerprint;
      if found then return v_event; end if;
    end if;
    raise;
end;
$$;

revoke all on function public.record_document_event(
  uuid, text, timestamptz, text, text, text, jsonb
) from public;
grant execute on function public.record_document_event(
  uuid, text, timestamptz, text, text, text, jsonb
) to authenticated;
