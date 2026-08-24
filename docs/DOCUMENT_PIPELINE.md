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

The embedding worker processes at most `JAFAR_EMBEDDING_BATCH_SIZE` chunks per
invocation. If unembedded chunks remain, it atomically requeues the same embed
job. Analyze cannot be claimed during this period.

## Analysis provenance

Every persisted document analysis includes `document_id`, `matter_id`, validated
citations, the complete source-chunk map (`id`, `page`, `chunk_index`), bounded
confidence, and `requires_lawyer_review = true`. Significant findings without a
valid `{claim, page, chunk_index}` citation are persisted as `manual_review`, not
as a completed analysis. A retry always inserts a new row; it never deletes or
overwrites an earlier successful analysis.

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
