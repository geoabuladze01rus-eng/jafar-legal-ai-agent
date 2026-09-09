-- Defense-in-depth for the deployed v3 queue. This migration is non-destructive:
-- existing rows are preserved, while future Ready/pending writes fail closed.

create or replace function public.touch_telegram_publication_queue_updated_at()
returns trigger
language plpgsql
set search_path = public, pg_catalog
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists telegram_publication_queue_touch_updated_at
  on public.telegram_publication_queue;
create trigger telegram_publication_queue_touch_updated_at
before update on public.telegram_publication_queue
for each row execute function public.touch_telegram_publication_queue_updated_at();

create or replace function public.enforce_telegram_ready_queue_safety()
returns trigger
language plpgsql
set search_path = public, pg_catalog
as $$
declare
  option_count integer;
begin
  if new.status <> 'Ready' or new.delivery_state <> 'pending' then
    return new;
  end if;

  if new.fact_check_status not in ('verified','not_required') then
    raise exception 'fact_check_not_verified' using errcode='P0001';
  end if;
  if new.legal_risk <> 'low' then
    raise exception 'legal_risk_not_low' using errcode='P0001';
  end if;
  if new.privacy_risk <> 'low' then
    raise exception 'privacy_risk_not_low' using errcode='P0001';
  end if;
  if new.current_case_risk is true then
    raise exception 'current_case_risk' using errcode='P0001';
  end if;
  if jsonb_typeof(coalesce(new.editorial_blockers,'null'::jsonb)) <> 'array'
     or jsonb_array_length(coalesce(new.editorial_blockers,'[]'::jsonb)) <> 0 then
    raise exception 'editorial_blockers_present' using errcode='P0001';
  end if;
  if new.content_fingerprint !~ '^[0-9a-f]{64}$' then
    raise exception 'content_fingerprint_invalid' using errcode='P0001';
  end if;
  if new.reconciliation_required is true or new.telegram_message_id is not null then
    raise exception 'delivery_not_clean' using errcode='P0001';
  end if;

  if new.publication_type = 'text' then
    if coalesce(btrim(new.content),'')='' or length(new.content)>4096 then
      raise exception 'text_invalid' using errcode='P0001';
    end if;
  elsif new.publication_type = 'photo' then
    if coalesce(btrim(new.visual_asset_key),'')=''
       or coalesce(btrim(new.visual_category),'')='' then
      raise exception 'approved_visual_required' using errcode='P0001';
    end if;
    if length(coalesce(new.caption,new.content,''))>1024 then
      raise exception 'caption_too_long' using errcode='P0001';
    end if;
  elsif new.publication_type in ('poll','quiz') then
    if coalesce(btrim(new.question),'')='' or length(new.question)>300 then
      raise exception 'question_invalid' using errcode='P0001';
    end if;
    if jsonb_typeof(coalesce(new.options,'null'::jsonb)) <> 'array' then
      raise exception 'options_invalid' using errcode='P0001';
    end if;
    option_count := jsonb_array_length(new.options);
    if option_count<2 or option_count>12 then
      raise exception 'options_invalid' using errcode='P0001';
    end if;
    if new.publication_type='quiz'
       and (
         jsonb_typeof(coalesce(new.correct_option_ids,'null'::jsonb)) <> 'array'
         or jsonb_array_length(coalesce(new.correct_option_ids,'[]'::jsonb))<1
       ) then
      raise exception 'correct_option_ids_invalid' using errcode='P0001';
    end if;
  else
    raise exception 'publication_type_invalid' using errcode='P0001';
  end if;

  return new;
end;
$$;

drop trigger if exists telegram_ready_queue_safety
  on public.telegram_publication_queue;
create trigger telegram_ready_queue_safety
before insert or update on public.telegram_publication_queue
for each row execute function public.enforce_telegram_ready_queue_safety();

revoke all on function public.enforce_telegram_ready_queue_safety()
  from public, anon, authenticated;
grant execute on function public.enforce_telegram_ready_queue_safety() to service_role;
revoke all on function public.touch_telegram_publication_queue_updated_at()
  from public, anon, authenticated;
grant execute on function public.touch_telegram_publication_queue_updated_at() to service_role;

-- Reassert the sensitive production boundary even in databases where these RPCs
-- were created manually before their source migrations existed.
revoke all on function public.get_jafar_worker_secret_for_publisher()
  from public, anon, authenticated;
revoke all on function public.get_telegram_bot_token_for_egress()
  from public, anon, authenticated;
revoke all on function public.telegram_bot_token_present()
  from public, anon, authenticated;
grant execute on function public.get_jafar_worker_secret_for_publisher() to service_role;
grant execute on function public.get_telegram_bot_token_for_egress() to service_role;
grant execute on function public.telegram_bot_token_present() to service_role;
