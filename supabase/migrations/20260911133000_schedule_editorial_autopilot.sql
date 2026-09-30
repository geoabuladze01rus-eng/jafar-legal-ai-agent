-- Generate due editorial-plan publications inside Supabase.
-- The Edge Function reads OPENAI_API_KEY from its own secret store.
-- No OpenAI or Telegram credentials are stored in this migration.

create or replace function public.run_jafar_editorial_autopilot_tick()
returns bigint
language plpgsql
security definer
set search_path = public, vault, net
as $$
declare
  project_url text;
  worker_secret text;
  request_id bigint;
begin
  select decrypted_secret into project_url
  from vault.decrypted_secrets
  where name = 'project_url'
  limit 1;

  select decrypted_secret into worker_secret
  from vault.decrypted_secrets
  where name = 'Jafar worker authentication secret'
  limit 1;

  if coalesce(btrim(project_url), '') = ''
     or coalesce(btrim(worker_secret), '') = '' then
    return null;
  end if;

  request_id := net.http_post(
    url := rtrim(project_url, '/') || '/functions/v1/telegram-editorial-autopilot-v1',
    headers := jsonb_build_object(
      'content-type', 'application/json',
      'x-jafar-worker-secret', worker_secret
    ),
    body := jsonb_build_object(
      'mode', 'generate',
      'limit', 1
    ),
    timeout_milliseconds := 240000
  );

  return request_id;
end;
$$;

revoke all on function public.run_jafar_editorial_autopilot_tick()
  from public, anon, authenticated;
grant execute on function public.run_jafar_editorial_autopilot_tick()
  to service_role;

do $$
begin
  if not exists (
    select 1 from cron.job
    where jobname = 'jafar-editorial-autopilot-v1'
  ) then
    perform cron.schedule(
      'jafar-editorial-autopilot-v1',
      '* * * * *',
      'select public.run_jafar_editorial_autopilot_tick();'
    );
  end if;
end $$;
