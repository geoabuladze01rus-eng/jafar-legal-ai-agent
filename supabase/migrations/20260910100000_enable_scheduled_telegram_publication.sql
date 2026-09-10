-- Allow Notion calendar cards in Scheduled status to enter the
-- protected internal Ready queue. All existing safety and delivery gates remain.

create or replace function public.upsert_telegram_publication_from_notion_v3(
  p_page_id text,
  p_row jsonb
)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
  v_publication_id text := btrim(coalesce(p_row->>'publication_id',''));
  v_type text := btrim(coalesce(p_row->>'publication_type',''));
  v_scheduled_at timestamptz;
  v_fact text := btrim(coalesce(p_row->>'fact_check_status',''));
  v_legal text := btrim(coalesce(p_row->>'legal_risk',''));
  v_privacy text := btrim(coalesce(p_row->>'privacy_risk',''));
  v_fingerprint text := btrim(coalesce(p_row->>'content_fingerprint',''));
  v_existing public.telegram_publication_queue%rowtype;
begin
  if coalesce(btrim(p_page_id),'') = '' then
    raise exception 'notion_page_id_required' using errcode='P0001';
  end if;
  if v_publication_id = '' then
    raise exception 'publication_id_required' using errcode='P0001';
  end if;
  if v_type not in ('text','photo','poll','quiz') then
    raise exception 'publication_type_invalid' using errcode='P0001';
  end if;
  if coalesce(p_row->>'status','') not in ('Ready','Scheduled') then
    raise exception 'status_not_scheduled' using errcode='P0001';
  end if;
  begin
    v_scheduled_at := (p_row->>'scheduled_at')::timestamptz;
  exception when others then
    raise exception 'scheduled_at_invalid' using errcode='P0001';
  end;
  if v_scheduled_at is null then
    raise exception 'scheduled_at_required' using errcode='P0001';
  end if;
  if v_fact not in ('verified','not_required') then
    raise exception 'fact_check_not_verified' using errcode='P0001';
  end if;
  if v_legal <> 'low' then
    raise exception 'legal_risk_not_low' using errcode='P0001';
  end if;
  if v_privacy <> 'low' then
    raise exception 'privacy_risk_not_low' using errcode='P0001';
  end if;
  if coalesce((p_row->>'current_case_risk')::boolean,false) then
    raise exception 'current_case_risk' using errcode='P0001';
  end if;
  if v_fingerprint !~ '^[0-9a-f]{64}$' then
    raise exception 'content_fingerprint_invalid' using errcode='P0001';
  end if;
  if jsonb_typeof(coalesce(p_row->'options','[]'::jsonb)) <> 'array' then
    raise exception 'options_invalid' using errcode='P0001';
  end if;
  if jsonb_typeof(coalesce(p_row->'correct_option_ids','[]'::jsonb)) <> 'array' then
    raise exception 'correct_option_ids_invalid' using errcode='P0001';
  end if;
  if jsonb_typeof(coalesce(p_row->'editorial_blockers','[]'::jsonb)) <> 'array' then
    raise exception 'editorial_blockers_invalid' using errcode='P0001';
  end if;
  if jsonb_array_length(coalesce(p_row->'editorial_blockers','[]'::jsonb)) <> 0 then
    raise exception 'editorial_blockers_present' using errcode='P0001';
  end if;

  select * into v_existing
  from public.telegram_publication_queue
  where publication_id = v_publication_id
  for update;

  if found then
    if v_existing.source_notion_page_id is not null and v_existing.source_notion_page_id <> p_page_id then
      raise exception 'publication_id_collision' using errcode='P0001';
    end if;
    if v_existing.delivery_state <> 'pending'
       or v_existing.telegram_message_id is not null
       or v_existing.status not in ('Ready','Review') then
      return 'blocked_existing_state';
    end if;

    update public.telegram_publication_queue
    set source_notion_page_id = p_page_id,
        status = 'Ready',
        publication_type = v_type,
        scheduled_at = v_scheduled_at,
        content = coalesce(p_row->>'content',''),
        caption = nullif(p_row->>'caption',''),
        question = nullif(p_row->>'question',''),
        options = coalesce(p_row->'options','[]'::jsonb),
        correct_option_ids = coalesce(p_row->'correct_option_ids','[]'::jsonb),
        explanation = nullif(p_row->>'explanation',''),
        visual_asset_key = nullif(p_row->>'visual_asset_key',''),
        visual_category = nullif(p_row->>'visual_category',''),
        fact_check_status = v_fact,
        legal_risk = v_legal,
        privacy_risk = v_privacy,
        current_case_risk = coalesce((p_row->>'current_case_risk')::boolean,false),
        editorial_blockers = coalesce(p_row->'editorial_blockers','[]'::jsonb),
        content_fingerprint = v_fingerprint,
        delivery_state = 'pending',
        reconciliation_required = false,
        delivery_payload_hash = null,
        last_error = null,
        notion_sync_pending = false,
        notion_synced_at = now(),
        notion_sync_error = null
    where publication_id = v_publication_id;
    return 'updated';
  end if;

  insert into public.telegram_publication_queue(
    publication_id, source_notion_page_id, status, publication_type, scheduled_at,
    content, caption, question, options, correct_option_ids, explanation,
    visual_asset_key, visual_category, fact_check_status, legal_risk, privacy_risk,
    current_case_risk, editorial_blockers, content_fingerprint,
    delivery_state, reconciliation_required, notion_sync_pending, notion_synced_at
  ) values (
    v_publication_id, p_page_id, 'Ready', v_type, v_scheduled_at,
    coalesce(p_row->>'content',''), nullif(p_row->>'caption',''), nullif(p_row->>'question',''),
    coalesce(p_row->'options','[]'::jsonb), coalesce(p_row->'correct_option_ids','[]'::jsonb), nullif(p_row->>'explanation',''),
    nullif(p_row->>'visual_asset_key',''), nullif(p_row->>'visual_category',''), v_fact, v_legal, v_privacy,
    coalesce((p_row->>'current_case_risk')::boolean,false), coalesce(p_row->'editorial_blockers','[]'::jsonb), v_fingerprint,
    'pending', false, false, now()
  );
  return 'inserted';
end;
$$;



revoke all on function public.upsert_telegram_publication_from_notion_v3(text,jsonb)
  from public, anon, authenticated;
grant execute on function public.upsert_telegram_publication_from_notion_v3(text,jsonb)
  to service_role;
