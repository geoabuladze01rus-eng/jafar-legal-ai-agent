begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_catalog;

select plan(25);

insert into public.matters (id, title, matter_type, owner_user_id)
values ('00000000-0000-0000-0000-000000000201', 'Pipeline test', 'general', 'pipeline-test-owner');

insert into public.documents (
  id, matter_id, filename, source, ocr_required, processing_status, max_retry_attempts
) values
  ('00000000-0000-0000-0000-000000000101', '00000000-0000-0000-0000-000000000201', 'success.pdf', 'test', true, 'ocr_processing', 3),
  ('00000000-0000-0000-0000-000000000102', null, 'manual.pdf', 'test', true, 'ocr_processing', 3),
  ('00000000-0000-0000-0000-000000000103', null, 'retry.pdf', 'test', true, 'queued', 3),
  ('00000000-0000-0000-0000-000000000104', null, 'explicit-review.pdf', 'test', true, 'ocr_processing', 3);

insert into public.document_ocr_jobs (
  document_id, status, attempts, locked_by, locked_at, lease_expires_at
) values
  ('00000000-0000-0000-0000-000000000101', 'processing', 1, 'ocr-worker', now(), now() + interval '5 minutes'),
  ('00000000-0000-0000-0000-000000000102', 'processing', 1, 'manual-worker', now(), now() + interval '5 minutes'),
  ('00000000-0000-0000-0000-000000000103', 'queued', 0, null, null, null),
  ('00000000-0000-0000-0000-000000000104', 'processing', 1, 'explicit-worker', now(), now() + interval '5 minutes');

insert into public.document_pages (
  document_id, page_number, extracted_text, ocr_used, ocr_confidence, status
) values
  ('00000000-0000-0000-0000-000000000101', 1, 'Grounded source', true, 0.99, 'completed'),
  ('00000000-0000-0000-0000-000000000102', 1, 'Unclear source', true, 0.40, 'manual_review'),
  ('00000000-0000-0000-0000-000000000104', 1, 'Readable but flagged', true, 0.99, 'completed');

select lives_ok(
  $$
    select public.complete_ocr_and_enqueue_pipeline(
      (select id from public.document_ocr_jobs where document_id = '00000000-0000-0000-0000-000000000101'),
      '00000000-0000-0000-0000-000000000101', 1, 1, false, 'ocr-worker'
    )
  $$,
  'successful OCR completion atomically hands off to the pipeline'
);
select is(
  (select status from public.document_ocr_jobs where document_id = '00000000-0000-0000-0000-000000000101'),
  'completed',
  'OCR job is completed'
);
select is(
  (select processing_status from public.documents where id = '00000000-0000-0000-0000-000000000101'),
  'pipeline_processing',
  'document is not fully completed after OCR'
);
select is(
  (select count(*) from public.document_pipeline_jobs where document_id = '00000000-0000-0000-0000-000000000101'),
  3::bigint,
  'all three pipeline jobs are created'
);
select lives_ok(
  $$
    select public.complete_ocr_and_enqueue_pipeline(
      (select id from public.document_ocr_jobs where document_id = '00000000-0000-0000-0000-000000000101'),
      '00000000-0000-0000-0000-000000000101', 1, 1, false, 'ocr-worker'
    )
  $$,
  'repeated OCR completion is idempotent'
);
select is(
  (select count(*) from public.document_pipeline_jobs where document_id = '00000000-0000-0000-0000-000000000101'),
  3::bigint,
  'repeated completion creates no duplicate jobs'
);

select lives_ok(
  $$
    select public.complete_ocr_and_enqueue_pipeline(
      (select id from public.document_ocr_jobs where document_id = '00000000-0000-0000-0000-000000000102'),
      '00000000-0000-0000-0000-000000000102', 1, 1, false, 'manual-worker'
    )
  $$,
  'page-level manual review is derived inside the completion RPC'
);
select is(
  (select status from public.document_ocr_jobs where document_id = '00000000-0000-0000-0000-000000000102'),
  'manual_review',
  'low-confidence OCR is terminal manual review'
);
select is(
  (select count(*) from public.document_pipeline_jobs where document_id = '00000000-0000-0000-0000-000000000102'),
  0::bigint,
  'manual-review OCR does not enqueue pipeline jobs'
);

select lives_ok(
  $$
    select public.complete_ocr_and_enqueue_pipeline(
      (select id from public.document_ocr_jobs where document_id = '00000000-0000-0000-0000-000000000104'),
      '00000000-0000-0000-0000-000000000104', 1, 1, true, 'explicit-worker'
    )
  $$,
  'an explicit manual-review decision completes without a pipeline handoff'
);
select is(
  (select count(*) from public.document_pipeline_jobs where document_id = '00000000-0000-0000-0000-000000000104'),
  0::bigint,
  'explicit manual review blocks every pipeline stage'
);

select is(
  (select attempts from public.claim_document_ocr_job('claim-worker', 60)),
  1,
  'OCR attempts increment on claim'
);
select is(
  (select locked_by from public.document_ocr_jobs where document_id = '00000000-0000-0000-0000-000000000103'),
  'claim-worker',
  'OCR claim records the lease owner'
);
select is_empty(
  $$ select * from public.claim_document_ocr_job('competing-ocr-worker', 60) $$,
  'a second OCR worker cannot claim an in-flight job'
);

update public.document_ocr_jobs
set lease_expires_at = now() - interval '1 second'
where document_id = '00000000-0000-0000-0000-000000000103';

select is(
  (select attempts from public.claim_document_ocr_job('recovery-worker', 60)),
  2,
  'an abandoned OCR claim is recovered and counts as a new attempt'
);

select is(
  (select stage from public.claim_document_pipeline_job('chunk-worker', 60)),
  'chunk',
  'chunk is the first claimable pipeline stage'
);
select is_empty(
  $$ select * from public.claim_document_pipeline_job('competing-pipeline-worker', 60) $$,
  'a second pipeline worker cannot claim the in-flight or blocked stages'
);
select lives_ok(
  $$
    select public.finish_document_pipeline_job(
      (select id from public.document_pipeline_jobs where document_id = '00000000-0000-0000-0000-000000000101' and stage = 'chunk'),
      '00000000-0000-0000-0000-000000000101', 'chunk-worker', 'completed', null
    )
  $$,
  'chunk completion is lease-fenced'
);

insert into public.document_chunks (document_id, chunk_index, content, source_page)
values ('00000000-0000-0000-0000-000000000101', 0, 'Grounded source', 1);

select is(
  (select stage from public.claim_document_pipeline_job('embed-worker', 60)),
  'embed',
  'embed becomes claimable only after chunk completion and chunk creation'
);
select throws_ok(
  $$
    select public.finish_document_pipeline_job(
      (select id from public.document_pipeline_jobs where document_id = '00000000-0000-0000-0000-000000000101' and stage = 'embed'),
      '00000000-0000-0000-0000-000000000101', 'embed-worker', 'completed', null
    )
  $$,
  'P0001',
  'embedding_stage_incomplete',
  'embed cannot complete while a chunk lacks an embedding'
);
select is_empty(
  $$ select * from public.claim_document_pipeline_job('blocked-analyze-worker', 60) $$,
  'analyze cannot be claimed while any chunk lacks an embedding'
);

update public.document_chunks
set embedding = array_fill(0::real, array[1536])::extensions.vector
where document_id = '00000000-0000-0000-0000-000000000101';

select lives_ok(
  $$
    select public.finish_document_pipeline_job(
      (select id from public.document_pipeline_jobs where document_id = '00000000-0000-0000-0000-000000000101' and stage = 'embed'),
      '00000000-0000-0000-0000-000000000101', 'embed-worker', 'completed', null
    )
  $$,
  'embed completes after every chunk has an embedding'
);

select is(
  (select stage from public.claim_document_pipeline_job('analyze-worker', 60)),
  'analyze',
  'analyze becomes claimable after every chunk has an embedding'
);

insert into public.ai_analyses (
  matter_id, document_id, analysis_type, result, status, citations,
  source_chunks, confidence, requires_lawyer_review, review_status, created_by
) values (
  '00000000-0000-0000-0000-000000000201',
  '00000000-0000-0000-0000-000000000101',
  'document_pipeline',
  '{"summary":"Grounded source"}'::jsonb,
  'completed',
  '[{"claim":"Grounded source","page":1,"chunk_index":0,"source_chunk_id":"test"}]'::jsonb,
  '[{"id":"test","page":1,"chunk_index":0}]'::jsonb,
  0.99,
  true,
  'pending',
  'document-pipeline-worker'
);

select lives_ok(
  $$
    select public.finish_document_pipeline_job(
      (select id from public.document_pipeline_jobs where document_id = '00000000-0000-0000-0000-000000000101' and stage = 'analyze'),
      '00000000-0000-0000-0000-000000000101', 'analyze-worker', 'completed', null
    )
  $$,
  'analyze completion is recorded'
);
select is(
  (select processing_status from public.documents where id = '00000000-0000-0000-0000-000000000101'),
  'completed',
  'document is completed only after analyze'
);

select * from finish();
rollback;
