create or replace function public.resume_document_embedding_job(
  p_job_id bigint,
  p_document_id uuid,
  p_worker_id text
)
returns void
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_job public.document_pipeline_jobs;
  v_attempts integer;
begin
  select * into v_job
  from public.document_pipeline_jobs j
  where j.id = p_job_id
    and j.document_id = p_document_id
  for update;

  if not found then
    raise exception 'pipeline_job_not_found';
  end if;
  if v_job.stage <> 'embed' then
    raise exception 'embedding_resume_stage_required';
  end if;
  if v_job.status <> 'processing'
    or v_job.locked_by is distinct from p_worker_id
    or v_job.lease_expires_at is null
    or v_job.lease_expires_at <= now() then
    raise exception 'stale_pipeline_worker_lease';
  end if;

  v_attempts := greatest(v_job.attempts - 1, 0);
  update public.document_pipeline_jobs
  set status = 'queued',
      attempts = v_attempts,
      available_at = now(),
      locked_at = null,
      lease_expires_at = null,
      locked_by = null,
      last_error = null,
      updated_at = now()
  where id = p_job_id;

  update public.documents
  set processing_status = 'pipeline_processing',
      retry_attempts = v_attempts,
      next_retry_at = null
  where id = p_document_id;
end;
$$;

revoke all on function public.resume_document_embedding_job(bigint, uuid, text)
  from public, anon, authenticated;
grant execute on function public.resume_document_embedding_job(bigint, uuid, text)
  to service_role;
