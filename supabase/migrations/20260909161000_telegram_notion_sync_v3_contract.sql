-- Reconcile the cloud Telegram objects that existed operationally before this
-- contract was committed. Defaults are deliberately non-sending. Every statement
-- preserves existing production rows and secrets.
create table if not exists public.telegram_publisher_config (
  id smallint primary key default 1 check (id = 1),
  enabled boolean not null default false,
  dry_run boolean not null default true,
  chat_id text not null default '-1004412524447',
  batch_size integer not null default 3 check (batch_size between 1 and 20),
  updated_at timestamptz not null default now()
);

insert into public.telegram_publisher_config(id, enabled, dry_run, chat_id, batch_size)
values (1, false, true, '-1004412524447', 3)
on conflict (id) do nothing;

alter table public.telegram_publisher_config enable row level security;
revoke all on public.telegram_publisher_config from public, anon, authenticated;
grant select, update on public.telegram_publisher_config to service_role;

create table if not exists public.telegram_publication_queue (
  publication_id text primary key,
  source_notion_page_id text,
  status text not null default 'Review'
    check (status in ('Draft','Review','Ready','In progress','Published','Error')),
  publication_type text not null
    check (publication_type in ('text','photo','poll','quiz')),
  scheduled_at timestamptz not null,
  content text not null default '',
  caption text,
  question text,
  options jsonb not null default '[]'::jsonb check (jsonb_typeof(options) = 'array'),
  correct_option_ids jsonb not null default '[]'::jsonb
    check (jsonb_typeof(correct_option_ids) = 'array'),
  explanation text,
  visual_asset_key text,
  visual_category text,
  fact_check_status text not null default 'pending'
    check (fact_check_status in ('pending','verified','unverified','failed','not_required')),
  legal_risk text not null default 'high'
    check (legal_risk in ('low','medium','high','critical')),
  privacy_risk text not null default 'high'
    check (privacy_risk in ('low','medium','high','critical')),
  current_case_risk boolean not null default true,
  editorial_blockers jsonb not null default '["unreviewed"]'::jsonb
    check (jsonb_typeof(editorial_blockers) = 'array'),
  content_fingerprint text not null check (content_fingerprint ~ '^[0-9a-f]{64}$'),
  delivery_state text not null default 'pending'
    check (delivery_state in ('pending','claimed','sent','failed','uncertain')),
  delivery_payload_hash text,
  reconciliation_required boolean not null default false,
  telegram_message_id bigint,
  published_at timestamptz,
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint telegram_queue_sent_requires_message_id
    check (delivery_state <> 'sent' or telegram_message_id is not null),
  constraint telegram_queue_payload_hash_format
    check (delivery_payload_hash is null or delivery_payload_hash ~ '^[0-9a-f]{64}$')
);

create index if not exists telegram_publication_queue_due_idx
  on public.telegram_publication_queue(scheduled_at, publication_id)
  where status='Ready' and delivery_state='pending' and reconciliation_required=false;

alter table public.telegram_publication_queue enable row level security;
revoke all on public.telegram_publication_queue from public, anon, authenticated;
grant select, insert, update on public.telegram_publication_queue to service_role;

create or replace function public.get_jafar_worker_secret_for_publisher()
returns text
language sql
stable
security definer
set search_path = public, vault
as $$
  select decrypted_secret
  from vault.decrypted_secrets
  where name='Jafar worker authentication secret'
  limit 1;
$$;

create or replace function public.get_telegram_bot_token_for_egress()
returns text
language sql
stable
security definer
set search_path = public, vault
as $$
  select decrypted_secret
  from vault.decrypted_secrets
  where name in ('telegram_bot_token','Telegram bot token')
  order by case when name='telegram_bot_token' then 0 else 1 end
  limit 1;
$$;

create or replace function public.telegram_bot_token_present()
returns boolean
language sql
stable
security definer
set search_path = public, vault
as $$
  select exists (
    select 1 from vault.decrypted_secrets
    where name in ('telegram_bot_token','Telegram bot token')
      and coalesce(btrim(decrypted_secret),'') <> ''
  );
$$;

revoke all on function public.get_jafar_worker_secret_for_publisher()
  from public, anon, authenticated;
revoke all on function public.get_telegram_bot_token_for_egress()
  from public, anon, authenticated;
revoke all on function public.telegram_bot_token_present()
  from public, anon, authenticated;
grant execute on function public.get_jafar_worker_secret_for_publisher() to service_role;
grant execute on function public.get_telegram_bot_token_for_egress() to service_role;
grant execute on function public.telegram_bot_token_present() to service_role;

create table if not exists public.telegram_notion_sync_config (
  id smallint primary key default 1 check (id = 1),
  enabled boolean not null default false,
  dry_run boolean not null default true,
  data_source_id text not null default '3d43c9c6-76b4-80d6-ac3e-000bf86b2d20',
  batch_size integer not null default 50 check (batch_size between 1 and 100),
  updated_at timestamptz not null default now()
);

insert into public.telegram_notion_sync_config(id, enabled, dry_run, data_source_id, batch_size)
values (1, false, true, '3d43c9c6-76b4-80d6-ac3e-000bf86b2d20', 50)
on conflict (id) do nothing;

alter table public.telegram_notion_sync_config enable row level security;
revoke all on public.telegram_notion_sync_config from public, anon, authenticated;
grant select, update on public.telegram_notion_sync_config to service_role;

alter table public.telegram_publication_queue
  add column if not exists notion_sync_pending boolean not null default false,
  add column if not exists notion_synced_at timestamptz,
  add column if not exists notion_sync_error text;

create unique index if not exists telegram_publication_queue_source_notion_page_uidx
  on public.telegram_publication_queue(source_notion_page_id)
  where source_notion_page_id is not null;

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
  if coalesce(p_row->>'status','') <> 'Ready' then
    raise exception 'status_not_ready' using errcode='P0001';
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

create or replace function public.get_telegram_notion_writeback_candidates_v3(p_limit integer default 50)
returns table(
  publication_id text,
  source_notion_page_id text,
  status text,
  delivery_state text,
  delivery_payload_hash text,
  telegram_message_id bigint,
  published_at timestamptz,
  reconciliation_required boolean,
  last_error text
)
language sql
stable
security definer
set search_path = public
as $$
  select q.publication_id, q.source_notion_page_id, q.status, q.delivery_state,
         q.delivery_payload_hash, q.telegram_message_id, q.published_at,
         q.reconciliation_required, q.last_error
  from public.telegram_publication_queue q
  where q.source_notion_page_id is not null
    and q.notion_sync_pending is true
    and q.status in ('In progress','Published','Error')
  order by q.updated_at asc
  limit greatest(1, least(coalesce(p_limit,50),100));
$$;

revoke all on function public.get_telegram_notion_writeback_candidates_v3(integer)
  from public, anon, authenticated;
grant execute on function public.get_telegram_notion_writeback_candidates_v3(integer)
  to service_role;

create or replace function public.mark_telegram_notion_synced_v3(p_publication_id text)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.telegram_publication_queue
  set notion_sync_pending=false,
      notion_synced_at=now(),
      notion_sync_error=null
  where publication_id=p_publication_id;
  if not found then
    raise exception 'queue_record_not_found' using errcode='P0001';
  end if;
end;
$$;

revoke all on function public.mark_telegram_notion_synced_v3(text)
  from public, anon, authenticated;
grant execute on function public.mark_telegram_notion_synced_v3(text)
  to service_role;

create or replace function public.mark_telegram_notion_sync_error_v3(
  p_publication_id text,
  p_error text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.telegram_publication_queue
  set notion_sync_pending=true,
      notion_sync_error=left(coalesce(p_error,'notion_sync_error'),1000)
  where publication_id=p_publication_id;
end;
$$;

revoke all on function public.mark_telegram_notion_sync_error_v3(text,text)
  from public, anon, authenticated;
grant execute on function public.mark_telegram_notion_sync_error_v3(text,text)
  to service_role;

create or replace function public.claim_telegram_publication_queue_v3(
  p_publication_id text,
  p_payload_hash text
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  q public.telegram_publication_queue%rowtype;
  claimed boolean;
  option_count integer;
begin
  if coalesce(btrim(p_publication_id), '') = '' then
    raise exception 'publication_id_required' using errcode = 'P0001';
  end if;
  if p_payload_hash is null or p_payload_hash !~ '^[0-9a-f]{64}$' then
    raise exception 'payload_hash_invalid' using errcode = 'P0001';
  end if;

  select * into q
  from public.telegram_publication_queue
  where publication_id = p_publication_id
  for update;
  if not found then return false; end if;

  if q.status <> 'Ready'
     or q.scheduled_at > now()
     or q.fact_check_status not in ('verified','not_required')
     or q.legal_risk <> 'low'
     or q.privacy_risk <> 'low'
     or q.current_case_risk is true
     or q.delivery_state <> 'pending'
     or q.reconciliation_required is true
     or q.telegram_message_id is not null
     or jsonb_array_length(q.editorial_blockers) <> 0 then
    return false;
  end if;

  if q.publication_type = 'text' then
    if coalesce(btrim(q.content), '') = '' then return false; end if;
  elsif q.publication_type = 'photo' then
    if coalesce(btrim(q.visual_asset_key), '') = ''
       or coalesce(btrim(q.visual_category), '') = '' then
      return false;
    end if;
    if not exists (
      select 1
      from public.telegram_visual_assets v
      where v.asset_key=q.visual_asset_key
        and v.category=q.visual_category
        and v.approved is true
        and v.active is true
        and coalesce(v.data_base64,'')<>''
    ) then
      return false;
    end if;
  elsif q.publication_type in ('poll','quiz') then
    if coalesce(btrim(q.question), '') = '' then return false; end if;
    option_count := jsonb_array_length(q.options);
    if option_count < 2 or option_count > 12 then return false; end if;
    if q.publication_type='quiz' and jsonb_array_length(q.correct_option_ids)<1 then
      return false;
    end if;
  else
    return false;
  end if;

  claimed := public.claim_telegram_publication(p_publication_id,p_payload_hash);
  if not claimed then return false; end if;

  update public.telegram_publication_queue
  set status='In progress',
      delivery_state='claimed',
      delivery_payload_hash=p_payload_hash,
      last_error=null,
      notion_sync_pending=true
  where publication_id=p_publication_id;

  return true;
end;
$$;

create or replace function public.mark_telegram_publication_sent_v3(
  p_publication_id text,
  p_telegram_message_id bigint
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if p_telegram_message_id is null or p_telegram_message_id <= 0 then
    raise exception 'telegram_message_id_invalid' using errcode='P0001';
  end if;

  perform public.mark_telegram_publication_sent(p_publication_id,p_telegram_message_id);

  update public.telegram_publication_queue
  set status='Published',
      delivery_state='sent',
      telegram_message_id=p_telegram_message_id,
      published_at=now(),
      reconciliation_required=false,
      last_error=null,
      notion_sync_pending=true
  where publication_id=p_publication_id
    and delivery_state='claimed';

  if not found then
    raise exception 'queue_claimed_record_not_found' using errcode='P0001';
  end if;
end;
$$;

create or replace function public.mark_telegram_publication_uncertain_v3(
  p_publication_id text,
  p_note text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  perform public.mark_telegram_publication_uncertain(
    p_publication_id,
    left(coalesce(p_note,'uncertain_delivery'),1000)
  );

  update public.telegram_publication_queue
  set status='Error',
      delivery_state='uncertain',
      reconciliation_required=true,
      last_error=left(coalesce(p_note,'uncertain_delivery'),1000),
      notion_sync_pending=true
  where publication_id=p_publication_id
    and delivery_state='claimed';

  if not found then
    raise exception 'queue_claimed_record_not_found' using errcode='P0001';
  end if;
end;
$$;

create or replace function public.mark_telegram_publication_failed_v3(
  p_publication_id text,
  p_error_code text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  perform public.mark_telegram_publication_failed(
    p_publication_id,
    left(coalesce(p_error_code,'pre_send_failed'),120)
  );

  update public.telegram_publication_queue
  set status='Error',
      delivery_state='failed',
      reconciliation_required=false,
      last_error=left(coalesce(p_error_code,'pre_send_failed'),1000),
      notion_sync_pending=true
  where publication_id=p_publication_id
    and delivery_state='claimed';

  if not found then
    raise exception 'queue_claimed_record_not_found' using errcode='P0001';
  end if;
end;
$$;

create or replace function public.run_telegram_notion_sync_v3_tick()
returns bigint
language plpgsql
security definer
set search_path = public, vault, net
as $$
declare
  cfg public.telegram_notion_sync_config%rowtype;
  project_url text;
  worker_secret text;
  request_id bigint;
begin
  select * into cfg
  from public.telegram_notion_sync_config
  where id=1;

  if not found or cfg.enabled is not true then
    return null;
  end if;

  select decrypted_secret into project_url
  from vault.decrypted_secrets
  where name='project_url'
  limit 1;

  select decrypted_secret into worker_secret
  from vault.decrypted_secrets
  where name='Jafar worker authentication secret'
  limit 1;

  if coalesce(btrim(project_url),'')=''
     or coalesce(btrim(worker_secret),'')='' then
    return null;
  end if;

  request_id := net.http_post(
    url := rtrim(project_url,'/') || '/functions/v1/telegram-notion-sync-v3',
    headers := jsonb_build_object(
      'content-type','application/json',
      'x-jafar-worker-secret',worker_secret
    ),
    body := jsonb_build_object(
      'mode','sync',
      'limit',greatest(1,least(coalesce(cfg.batch_size,50),100))
    ),
    timeout_milliseconds := 20000
  );

  return request_id;
end;
$$;

revoke all on function public.run_telegram_notion_sync_v3_tick()
  from public, anon, authenticated;
grant execute on function public.run_telegram_notion_sync_v3_tick()
  to service_role;

do $$
begin
  if not exists (
    select 1 from cron.job where jobname='jafar-telegram-notion-sync-v3'
  ) then
    perform cron.schedule(
      'jafar-telegram-notion-sync-v3',
      '*/5 * * * *',
      'select public.run_telegram_notion_sync_v3_tick();'
    );
  end if;
end $$;

create or replace function public.run_telegram_publisher_v3_tick()
returns bigint
language plpgsql
security definer
set search_path = public, vault, net
as $$
declare
  cfg public.telegram_publisher_config%rowtype;
  project_url text;
  worker_secret text;
  request_id bigint;
begin
  select * into cfg from public.telegram_publisher_config where id=1;
  if not found or cfg.enabled is not true then return null; end if;

  select decrypted_secret into project_url
  from vault.decrypted_secrets where name='project_url' limit 1;
  select decrypted_secret into worker_secret
  from vault.decrypted_secrets
  where name='Jafar worker authentication secret' limit 1;

  if coalesce(btrim(project_url),'')='' or coalesce(btrim(worker_secret),'')='' then
    return null;
  end if;

  request_id := net.http_post(
    url := rtrim(project_url,'/') || '/functions/v1/telegram-publisher-v3',
    headers := jsonb_build_object(
      'content-type','application/json',
      'x-jafar-worker-secret',worker_secret
    ),
    body := jsonb_build_object(
      'mode','publish',
      'limit',greatest(1,least(coalesce(cfg.batch_size,3),20))
    ),
    timeout_milliseconds := 80000
  );
  return request_id;
end;
$$;

revoke all on function public.run_telegram_publisher_v3_tick()
  from public, anon, authenticated;
grant execute on function public.run_telegram_publisher_v3_tick() to service_role;

do $$
begin
  if not exists (select 1 from cron.job where jobname='jafar-telegram-publisher-v3') then
    perform cron.schedule(
      'jafar-telegram-publisher-v3',
      '* * * * *',
      'select public.run_telegram_publisher_v3_tick();'
    );
  end if;
end $$;
