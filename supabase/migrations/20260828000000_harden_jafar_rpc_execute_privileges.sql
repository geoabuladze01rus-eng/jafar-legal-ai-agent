-- Harden Jafar RPC execute privileges; platform functions are excluded.

REVOKE EXECUTE ON FUNCTION public.claim_document_ocr_job_for_owner(text,text,integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_document_ocr_job_for_owner(text,text,integer) TO service_role;

REVOKE EXECUTE ON FUNCTION public.claim_document_ocr_job(text,integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_document_ocr_job(text,integer) TO service_role;

REVOKE EXECUTE ON FUNCTION public.claim_document_pipeline_job(text,integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_document_pipeline_job(text,integer) TO service_role;

REVOKE EXECUTE ON FUNCTION public.claim_document_recovery_jobs(text,integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_document_recovery_jobs(text,integer) TO service_role;

REVOKE EXECUTE ON FUNCTION public.claim_due_failed_documents(integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_due_failed_documents(integer) TO service_role;

REVOKE EXECUTE ON FUNCTION public.claim_due_telegram_publications(timestamp with time zone,integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_due_telegram_publications(timestamp with time zone,integer) TO service_role;

REVOKE EXECUTE ON FUNCTION public.claim_email_processing(text,text,text,timestamp with time zone) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_email_processing(text,text,text,timestamp with time zone) TO service_role;

REVOKE EXECUTE ON FUNCTION public.claim_failed_document_for_retry(text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_failed_document_for_retry(text) TO service_role;

REVOKE EXECUTE ON FUNCTION public.complete_email_processing(text,boolean) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.complete_email_processing(text,boolean) TO service_role;

REVOKE EXECUTE ON FUNCTION public.complete_ocr_and_enqueue_pipeline(bigint,uuid,integer,integer,boolean,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.complete_ocr_and_enqueue_pipeline(bigint,uuid,integer,integer,boolean,text) TO service_role;

REVOKE EXECUTE ON FUNCTION public.complete_ocr_and_enqueue_pipeline(bigint,uuid,integer,integer,boolean) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.complete_ocr_and_enqueue_pipeline(bigint,uuid,integer,integer,boolean) TO service_role;

REVOKE EXECUTE ON FUNCTION public.detect_recovery_worker_incident(interval) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.detect_recovery_worker_incident(interval) TO service_role;

REVOKE EXECUTE ON FUNCTION public.enqueue_document_ocr_job(uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.enqueue_document_ocr_job(uuid) TO service_role;

REVOKE EXECUTE ON FUNCTION public.enqueue_document_pipeline(uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.enqueue_document_pipeline(uuid) TO service_role;

REVOKE EXECUTE ON FUNCTION public.enqueue_due_document_recovery(integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.enqueue_due_document_recovery(integer) TO service_role;

REVOKE EXECUTE ON FUNCTION public.fail_document_ocr_job(bigint,uuid,text,text,boolean,timestamp with time zone) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.fail_document_ocr_job(bigint,uuid,text,text,boolean,timestamp with time zone) TO service_role;

REVOKE EXECUTE ON FUNCTION public.finish_document_pipeline_job(bigint,uuid,text,text,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.finish_document_pipeline_job(bigint,uuid,text,text,text) TO service_role;

REVOKE EXECUTE ON FUNCTION public.finish_document_recovery_job(uuid,text,boolean,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.finish_document_recovery_job(uuid,text,boolean,text) TO service_role;

REVOKE EXECUTE ON FUNCTION public.finish_document_retry(text,boolean,text,timestamp with time zone) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.finish_document_retry(text,boolean,text,timestamp with time zone) TO service_role;

REVOKE EXECUTE ON FUNCTION public.finish_document_retry(text,boolean,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.finish_document_retry(text,boolean,text) TO service_role;

REVOKE EXECUTE ON FUNCTION public.heartbeat_recovery_job(uuid,text,integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.heartbeat_recovery_job(uuid,text,integer) TO service_role;

REVOKE EXECUTE ON FUNCTION public.match_document_chunks(vector,integer,uuid) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.match_document_chunks(vector,integer,uuid) TO authenticated;

REVOKE EXECUTE ON FUNCTION public.persist_email_processing(jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.persist_email_processing(jsonb) TO service_role;

REVOKE EXECUTE ON FUNCTION public.record_document_event(uuid,text,timestamp with time zone,text,text,text,jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.record_document_event(uuid,text,timestamp with time zone,text,text,text,jsonb) TO service_role;

REVOKE EXECUTE ON FUNCTION public.record_recovery_worker_run(timestamp with time zone,timestamp with time zone,integer,text,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.record_recovery_worker_run(timestamp with time zone,timestamp with time zone,integer,text,text) TO service_role;

REVOKE EXECUTE ON FUNCTION public.requeue_expired_recovery_jobs(integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.requeue_expired_recovery_jobs(integer) TO service_role;

REVOKE EXECUTE ON FUNCTION public.requeue_stale_telegram_publications(timestamp with time zone,integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.requeue_stale_telegram_publications(timestamp with time zone,integer) TO service_role;

REVOKE EXECUTE ON FUNCTION public.resolve_recovery_worker_incidents() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.resolve_recovery_worker_incidents() TO service_role;

REVOKE EXECUTE ON FUNCTION public.resolve_telegram_comment(bigint,text,bigint,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.resolve_telegram_comment(bigint,text,bigint,text) TO service_role;

REVOKE EXECUTE ON FUNCTION public.resume_document_embedding_job(bigint,uuid,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.resume_document_embedding_job(bigint,uuid,text) TO service_role;

REVOKE EXECUTE ON FUNCTION public.retry_document_pipeline_job(bigint,uuid,text,text,timestamp with time zone) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.retry_document_pipeline_job(bigint,uuid,text,text,timestamp with time zone) TO service_role;

REVOKE EXECUTE ON FUNCTION public.run_document_recovery_tick(integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.run_document_recovery_tick(integer) TO service_role;

REVOKE EXECUTE ON FUNCTION public.schedule_jafar_document_workers() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.schedule_jafar_document_workers() TO service_role;

REVOKE EXECUTE ON FUNCTION public.set_document_processing_status(text,text,text,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.set_document_processing_status(text,text,text,text) TO service_role;

REVOKE EXECUTE ON FUNCTION public.worker_heartbeat(text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.worker_heartbeat(text) TO service_role;
