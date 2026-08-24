-- Run the internal document workers every 30 seconds.
-- Credentials are read from Vault at invocation time; do not hardcode keys in cron definitions.
select cron.schedule(
  'jafar-document-ocr-worker',
  '30 seconds',
  $$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets where name = 'project_url') || '/functions/v1/document-ocr-worker-v4',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'apikey', (select decrypted_secret from vault.decrypted_secrets where name = 'jafar_worker_secret')
    ),
    body := jsonb_build_object('source', 'pg_cron', 'requested_at', now()),
    timeout_milliseconds := 120000
  );
  $$
);

select cron.schedule(
  'jafar-document-pipeline-worker',
  '30 seconds',
  $$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets where name = 'project_url') || '/functions/v1/document-pipeline-worker-v3',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'apikey', (select decrypted_secret from vault.decrypted_secrets where name = 'jafar_worker_secret')
    ),
    body := jsonb_build_object('source', 'pg_cron', 'requested_at', now()),
    timeout_milliseconds := 120000
  );
  $$
);
