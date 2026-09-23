-- Text-only editorial autopilot: no image or video generation.
-- The service-role-only RPC enqueues text posts and text quizzes directly.

create or replace function public.enqueue_jafar_editorial_text_publication_v1(
  p_plan_id uuid,
  p_text_response jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  plan_row public.jafar_editorial_plan%rowtype;
  text_payload jsonb := p_text_response;
  generated jsonb;
  content_text text;
  question_text text;
  explanation_text text;
  options_json jsonb;
  correct_ids_json jsonb;
  base_id text;
  publication_id text;
  text_publication_id text;
  quiz_publication_id text;
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

  content_text := left(trim(coalesce(generated->>'content', '')), 4096);
  question_text := left(trim(coalesce(generated->>'question', '')), 300);
  explanation_text := left(trim(coalesce(generated->>'explanation', '')), 200);
  options_json := coalesce(generated->'options', '[]'::jsonb);
  correct_ids_json := coalesce(generated->'correct_option_ids', '[]'::jsonb);

  if content_text = '' then
    return jsonb_build_object('ok', false, 'error', 'generated_text_missing');
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
  text_publication_id := base_id || ':text';
  quiz_publication_id := base_id || ':quiz';

  content_fingerprint := encode(digest(
    jsonb_build_object(
      'publication_type', 'text',
      'content', content_text
    )::text,
    'sha256'
  ), 'hex');

  insert into public.telegram_publication_queue (
    publication_id, source_notion_page_id, status, publication_type, scheduled_at,
    content, fact_check_status, legal_risk, privacy_risk, current_case_risk,
    editorial_blockers, content_fingerprint
  )
  values (
    text_publication_id, base_id, 'Ready', 'text', plan_row.scheduled_at,
    content_text, 'not_required', 'low', 'low', false, '[]'::jsonb, content_fingerprint
  )
  on conflict (publication_id) do nothing;
  inserted_ids := array_append(inserted_ids, text_publication_id);

  if plan_row.publication_type = 'quiz' then
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
    publication_id := text_publication_id;
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

revoke all on function public.enqueue_jafar_editorial_text_publication_v1(uuid, jsonb)
  from public, anon, authenticated;
grant execute on function public.enqueue_jafar_editorial_text_publication_v1(uuid, jsonb)
  to service_role;
