create table if not exists public.jafar_editorial_plan (
  plan_id uuid primary key default gen_random_uuid(),
  slot_key text not null,
  scheduled_at timestamptz not null,
  publication_type text not null check (publication_type in ('photo', 'quiz')),
  theme text not null,
  prompt_context text not null default '',
  status text not null default 'pending' check (status in ('pending', 'processing', 'generated', 'skipped', 'error')),
  generated_publication_id text,
  generated_at timestamptz,
  attempt_count integer not null default 0 check (attempt_count >= 0),
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (slot_key, scheduled_at)
);

create index if not exists jafar_editorial_plan_due_idx
  on public.jafar_editorial_plan (status, scheduled_at);

alter table public.jafar_editorial_plan enable row level security;
revoke all on table public.jafar_editorial_plan from public, anon, authenticated;
grant select on table public.jafar_editorial_plan to service_role;

create or replace function public.jafar_editorial_plan_touch_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists jafar_editorial_plan_touch on public.jafar_editorial_plan;
create trigger jafar_editorial_plan_touch
before update on public.jafar_editorial_plan
for each row execute function public.jafar_editorial_plan_touch_updated_at();

revoke all on function public.jafar_editorial_plan_touch_updated_at() from public, anon, authenticated;

with slots(slot_key, day_of_week, local_time, publication_type, theme, prompt_context) as (
  values
    ('tuesday-expert', 2, time '12:00', 'photo', 'Задержание и первые часы после него', 'Экспертный разбор для широкой аудитории: права человека, типичные ошибки, практический вывод.'),
    ('wednesday-practical', 3, time '12:00', 'photo', 'Что делать, если вызывают на допрос', 'Пошаговый практический материал без индивидуальной юридической консультации и без обещаний результата.'),
    ('thursday-practice', 4, time '12:00', 'photo', 'Как суд оценивает доказательства', 'Разбор типовой судебной ситуации без реальных дел, персональных данных и непроверяемых утверждений.'),
    ('friday-author', 5, time '12:00', 'photo', 'Мнение юриста и бывшего следователя', 'Авторская колонка Артура Чернова: спокойно, конкретно, с отделением фактов от мнения.'),
    ('saturday-quiz', 6, time '11:00', 'quiz', 'Криминалистика и уголовный процесс', 'Образовательный квиз на 2–4 варианта ответа с коротким объяснением правильного варианта.')
),
base as (
  select (now() at time zone 'Europe/Moscow')::date as today
),
next_slots as (
  select
    s.*,
    case
      when (
        (
          b.today
          + ((s.day_of_week - extract(isodow from b.today)::integer + 7) % 7)
        )::date + s.local_time
      ) at time zone 'Europe/Moscow' > now()
      then (
        (
          b.today
          + ((s.day_of_week - extract(isodow from b.today)::integer + 7) % 7)
        )::date + s.local_time
      )
      else (
        (
          b.today
          + ((s.day_of_week - extract(isodow from b.today)::integer + 7) % 7)
        )::date + s.local_time + interval '7 days'
      )
    end as local_datetime
  from slots s cross join base b
)
insert into public.jafar_editorial_plan (
  slot_key, scheduled_at, publication_type, theme, prompt_context
)
select
  slot_key,
  local_datetime at time zone 'Europe/Moscow',
  publication_type,
  theme,
  prompt_context
from next_slots
on conflict (slot_key, scheduled_at) do nothing;

create or replace function public.enqueue_jafar_editorial_publication_v1(
  p_plan_id uuid,
  p_text_response jsonb,
  p_image_response jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  plan_row public.jafar_editorial_plan%rowtype;
  text_payload jsonb := p_text_response;
  image_payload jsonb := p_image_response;
  generated jsonb;
  content_text text;
  caption_text text;
  question_text text;
  explanation_text text;
  image_b64 text;
  asset_key text;
  base_id text;
  publication_id text;
  visual_publication_id text;
  quiz_publication_id text;
  options_json jsonb;
  correct_ids_json jsonb;
  content_fingerprint text;
  inserted_ids text[] := '{}';
begin
  select *
    into plan_row
  from public.jafar_editorial_plan
  where plan_id = p_plan_id
  for update;

  if not found then
    return jsonb_build_object('ok', false, 'error', 'plan_not_found');
  end if;

  if plan_row.status <> 'pending' then
    return jsonb_build_object('ok', false, 'error', 'plan_not_pending', 'status', plan_row.status);
  end if;

  if text_payload ? 'body' and jsonb_typeof(text_payload->'body') = 'object' then
    text_payload := text_payload->'body';
  end if;
  if image_payload ? 'body' and jsonb_typeof(image_payload->'body') = 'object' then
    image_payload := image_payload->'body';
  end if;

  begin
    generated := coalesce(
      nullif(text_payload #>> '{choices,0,message,content}', ''),
      nullif(text_payload #>> '{output,0,content,0,text}', ''),
      nullif(text_payload->>'output_text', ''),
      nullif(text_payload->>'result', '')
    )::jsonb;
  exception when others then
    generated := null;
  end;

  if generated is null then
    return jsonb_build_object('ok', false, 'error', 'generated_json_missing');
  end if;

  content_text := left(trim(coalesce(generated->>'content', generated->>'body', '')), 4096);
  caption_text := left(trim(coalesce(generated->>'caption', content_text)), 1024);
  question_text := left(trim(coalesce(generated->>'question', '')), 300);
  explanation_text := left(trim(coalesce(generated->>'explanation', '')), 200);
  options_json := coalesce(generated->'options', '[]'::jsonb);
  correct_ids_json := coalesce(generated->'correct_option_ids', '[]'::jsonb);

  begin
    image_b64 := coalesce(
      nullif(image_payload #>> '{data,0,b64_json}', ''),
      nullif(image_payload #>> '{data,0,base64}', ''),
      nullif(image_payload->>'b64_json', '')
    );
  exception when others then
    image_b64 := null;
  end;

  if image_b64 is null or length(image_b64) = 0 then
    return jsonb_build_object('ok', false, 'error', 'generated_image_missing');
  end if;

  if plan_row.publication_type = 'quiz' then
    if question_text = '' or jsonb_typeof(options_json) <> 'array'
       or jsonb_array_length(options_json) < 2 or jsonb_array_length(options_json) > 12
       or jsonb_typeof(correct_ids_json) <> 'array' or jsonb_array_length(correct_ids_json) <> 1 then
      return jsonb_build_object('ok', false, 'error', 'generated_quiz_invalid');
    end if;
  elsif plan_row.publication_type <> 'photo' then
    return jsonb_build_object('ok', false, 'error', 'unsupported_publication_type');
  end if;

  base_id := 'autopilot:' || p_plan_id::text;
  asset_key := base_id || ':visual';
  visual_publication_id := base_id || ':photo';
  quiz_publication_id := base_id || ':quiz';

  insert into public.telegram_visual_assets (
    asset_key, category, version, filename, mime_type, sha256, data_base64, approved, active
  )
  values (
    asset_key,
    'editorial',
    1,
    'jafar-' || replace(p_plan_id::text, '-', '') || '.jpg',
    'image/jpeg',
    encode(digest(decode(image_b64, 'base64'), 'sha256'), 'hex'),
    image_b64,
    true,
    true
  )
  on conflict (asset_key) do update set
    sha256 = excluded.sha256,
    data_base64 = excluded.data_base64,
    approved = true,
    active = true,
    updated_at = now();

  if plan_row.publication_type = 'quiz' then
    content_fingerprint := encode(digest(
      jsonb_build_object('publication_type', 'photo', 'caption', caption_text, 'asset_key', asset_key)::text,
      'sha256'
    ), 'hex');

    insert into public.telegram_publication_queue (
      publication_id, source_notion_page_id, status, publication_type, scheduled_at,
      content, caption, visual_asset_key, visual_category,
      fact_check_status, legal_risk, privacy_risk, current_case_risk,
      editorial_blockers, content_fingerprint
    )
    values (
      visual_publication_id, base_id, 'Ready', 'photo', plan_row.scheduled_at,
      content_text, caption_text, asset_key, 'editorial',
      'not_required', 'low', 'low', false, '[]'::jsonb, content_fingerprint
    )
    on conflict (publication_id) do nothing;
    inserted_ids := array_append(inserted_ids, visual_publication_id);

    content_fingerprint := encode(digest(
      jsonb_build_object(
        'publication_type', 'quiz',
        'question', question_text,
        'options', options_json,
        'correct_option_ids', correct_ids_json,
        'explanation', explanation_text
      )::text,
      'sha256'
    ), 'hex');

    insert into public.telegram_publication_queue (
      publication_id, source_notion_page_id, status, publication_type, scheduled_at,
      content, question, options, correct_option_ids, explanation,
      fact_check_status, legal_risk, privacy_risk, current_case_risk,
      editorial_blockers, content_fingerprint
    )
    values (
      quiz_publication_id, base_id, 'Ready', 'quiz', plan_row.scheduled_at + interval '5 seconds',
      content_text, question_text, options_json, correct_ids_json, explanation_text,
      'not_required', 'low', 'low', false, '[]'::jsonb, content_fingerprint
    )
    on conflict (publication_id) do nothing;
    inserted_ids := array_append(inserted_ids, quiz_publication_id);
    publication_id := quiz_publication_id;
  else
    content_fingerprint := encode(digest(
      jsonb_build_object('publication_type', 'photo', 'caption', caption_text, 'asset_key', asset_key)::text,
      'sha256'
    ), 'hex');

    insert into public.telegram_publication_queue (
      publication_id, source_notion_page_id, status, publication_type, scheduled_at,
      content, caption, visual_asset_key, visual_category,
      fact_check_status, legal_risk, privacy_risk, current_case_risk,
      editorial_blockers, content_fingerprint
    )
    values (
      visual_publication_id, base_id, 'Ready', 'photo', plan_row.scheduled_at,
      content_text, caption_text, asset_key, 'editorial',
      'not_required', 'low', 'low', false, '[]'::jsonb, content_fingerprint
    )
    on conflict (publication_id) do nothing;
    inserted_ids := array_append(inserted_ids, visual_publication_id);
    publication_id := visual_publication_id;
  end if;

  update public.jafar_editorial_plan
  set status = 'generated',
      generated_publication_id = publication_id,
      generated_at = now(),
      attempt_count = attempt_count + 1,
      last_error = null
  where plan_id = p_plan_id;

  insert into public.jafar_editorial_plan (
    slot_key, scheduled_at, publication_type, theme, prompt_context
  )
  values (
    plan_row.slot_key,
    plan_row.scheduled_at + interval '7 days',
    plan_row.publication_type,
    plan_row.theme,
    plan_row.prompt_context
  )
  on conflict (slot_key, scheduled_at) do nothing;

  return jsonb_build_object(
    'ok', true,
    'plan_id', p_plan_id,
    'publication_id', publication_id,
    'inserted_publication_ids', to_jsonb(inserted_ids)
  );
exception when others then
  update public.jafar_editorial_plan
  set status = 'error',
      attempt_count = attempt_count + 1,
      last_error = left(sqlerrm, 900)
  where plan_id = p_plan_id;
  return jsonb_build_object('ok', false, 'error', 'enqueue_failed');
end;
$$;

revoke all on function public.enqueue_jafar_editorial_publication_v1(uuid, jsonb, jsonb) from public, anon, authenticated;
grant execute on function public.enqueue_jafar_editorial_publication_v1(uuid, jsonb, jsonb) to service_role;
