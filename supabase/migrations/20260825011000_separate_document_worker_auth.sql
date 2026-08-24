-- The Supabase gateway credential and the application worker secret have
-- different purposes. The gateway receives a publishable key in `apikey`;
-- the Edge Function authenticates the caller with `x-jafar-worker-secret`.

create or replace function public.schedule_jafar_document_workers()
returns void
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
begin
  if not exists (select 1 from vault.secrets where name = 'project_url') then
    raise exception 'missing Vault secret: project_url';
  end if;
  if not exists (select 1 from vault.secrets where name = 'supabase_publishable_key') then
    raise exception 'missing Vault secret: supabase_publishable_key';
  end if;
  if not exists (select 1 from vault.secrets where name = 'jafar_worker_secret') then
    raise exception 'missing Vault secret: jafar_worker_secret';
  end if;

  perform cron.unschedule(jobid)
  from cron.job
  where jobname in ('jafar-document-ocr-worker', 'jafar-document-pipeline-worker');

  perform cron.schedule(
    'jafar-document-ocr-worker',
    '30 seconds',
    $cron$
    select net.http_post(
      url := (select decrypted_secret from vault.decrypted_secrets where name = 'project_url')
        || '/functions/v1/document-ocr-worker-v4',
      headers := jsonb_build_object(
        'Content-Type', 'application/json',
        'apikey', (select decrypted_secret from vault.decrypted_secrets where name = 'supabase_publishable_key'),
        'x-jafar-worker-secret', (select decrypted_secret from vault.decrypted_secrets where name = 'jafar_worker_secret')
      ),
      body := jsonb_build_object('source', 'pg_cron', 'requested_at', now()),
      timeout_milliseconds := 120000
    );
    $cron$
  );

  perform cron.schedule(
    'jafar-document-pipeline-worker',
    '30 seconds',
    $cron$
    select net.http_post(
      url := (select decrypted_secret from vault.decrypted_secrets where name = 'project_url')
        || '/functions/v1/document-pipeline-worker-v3',
      headers := jsonb_build_object(
        'Content-Type', 'application/json',
        'apikey', (select decrypted_secret from vault.decrypted_secrets where name = 'supabase_publishable_key'),
        'x-jafar-worker-secret', (select decrypted_secret from vault.decrypted_secrets where name = 'jafar_worker_secret')
      ),
      body := jsonb_build_object('source', 'pg_cron', 'requested_at', now()),
      timeout_milliseconds := 120000
    );
    $cron$
  );
end;
$$;

revoke all on function public.schedule_jafar_document_workers() from public, anon, authenticated;
grant execute on function public.schedule_jafar_document_workers() to service_role;

do $$
begin
  -- Remove any legacy schedules that used JAFAR_WORKER_SECRET as the gateway
  -- apikey. When required secrets are absent, leave workers unscheduled rather
  -- than issuing unauthenticated or semantically invalid requests.
  perform cron.unschedule(jobid)
  from cron.job
  where jobname in ('jafar-document-ocr-worker', 'jafar-document-pipeline-worker');

  if exists (select 1 from vault.secrets where name = 'project_url')
    and exists (select 1 from vault.secrets where name = 'supabase_publishable_key')
    and exists (select 1 from vault.secrets where name = 'jafar_worker_secret') then
    perform public.schedule_jafar_document_workers();
  else
    raise warning 'Jafar document workers are unscheduled: provision project_url, supabase_publishable_key, and jafar_worker_secret in Vault, then call schedule_jafar_document_workers()';
  end if;
end;
$$;
