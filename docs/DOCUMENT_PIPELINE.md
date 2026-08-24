# Production document pipeline

The production path is:

`queued -> ocr_processing -> pipeline_processing -> completed`

`document_ocr_jobs.status = completed` is the durable OCR-completion signal. A
document reaches `documents.processing_status = completed` only after `chunk`,
`embed`, and `analyze` have all completed. `manual_review` is terminal until a
lawyer or an explicit recovery workflow requeues the affected job. The legacy
`stored`, `processing`, and `failed` states remain valid for older clients.

## Atomic boundaries

- `claim_document_ocr_job` increments `attempts`, records `locked_by`, and moves
  the document to `ocr_processing` in one transaction.
- `complete_ocr_and_enqueue_pipeline` completes OCR and creates the unique
  `chunk`, `embed`, and `analyze` jobs in one transaction. Repeated completion
  calls do not create duplicate jobs.
- `claim_document_pipeline_job` uses `FOR UPDATE SKIP LOCKED` and only exposes a
  stage when all of its prerequisites are complete. Analyze additionally
  requires every document chunk to have an embedding.
- `finish_document_pipeline_job` fences stale workers with `locked_by` and only
  marks the document `completed` after a successfully validated analyze stage.
- OpenAI network failures, timeouts, 408, 409, 429, and 5xx responses use bounded
  exponential retry with jitter. HTTP 400, 401, 403, and 404, malformed model
  output, and non-recoverable schema validation errors are not retried. If
  transient request retries are exhausted, the pipeline job is atomically
  returned to `queued` with a database backoff timestamp until
  `max_retry_attempts` is reached. Expired leases follow the same limit.

The embedding worker processes at most `JAFAR_EMBEDDING_BATCH_SIZE` chunks per
invocation. If unembedded chunks remain, it atomically requeues the same embed
job. Already populated embeddings are selected out and cannot be overwritten.
A 250-chunk document therefore completes as 100 + 100 + 50, with the first two
batches requeued. Analyze cannot be claimed during this period.

## Analysis provenance

Every persisted document analysis includes `document_id`, `matter_id`, validated
citations, the complete source-chunk map (`id`, `page`, `chunk_index`), bounded
confidence, and `requires_lawyer_review = true`. Significant findings without a
valid `{claim, page, chunk_index}` citation are persisted as `manual_review`, not
as a completed analysis. Each result carries its pipeline job ID; a lease replay
reuses an already persisted terminal result instead of inserting a duplicate.
Earlier successful analyses are never deleted or overwritten.

## Worker authentication and deployment

Both worker functions use `verify_jwt = false` because they authenticate the
application caller themselves. Scheduled requests must send:

- `apikey`: the Supabase publishable key, for gateway semantics;
- `x-jafar-worker-secret`: the independent `JAFAR_WORKER_SECRET` value.

Provision `project_url`, `supabase_publishable_key`, and `jafar_worker_secret` in
Supabase Vault without committing or printing their values. The corrective
migration removes legacy schedules. When all three names exist it schedules the
workers automatically; otherwise it leaves them safely unscheduled. After
provisioning missing values, run `select public.schedule_jafar_document_workers();`
as `service_role` or an administrative database role.

Deploy the database migrations before the two Edge Functions so the new RPC
signatures and lease-fencing columns exist when the workers start.

`JAFAR_OPENAI_MAX_ATTEMPTS`, `JAFAR_OPENAI_TIMEOUT_MS`, and
`JAFAR_PIPELINE_MAX_RETRIES` are validated runtime settings. Each OpenAI attempt
also sends a unique `X-Client-Request-Id`; neither credentials nor document text
is included in that identifier. Structured request logs contain only request ID,
stage, attempt, HTTP status, latency, and error category. They never contain API
keys, worker/service-role secrets, request bodies, or document text.
