create or replace function public.retry_document_pipeline_job(
  p_job_id bigint,
  p_document_id uuid,
  p_worker_id text,
  p_error text,
  p_available_at timestamptz
)
returns void
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_job public.document_pipeline_jobs;
  v_max_retries integer;
  v_retry_at timestamptz;
begin
  select * into v_job
  from public.document_pipeline_jobs j
  where j.id = p_job_id
    and j.document_id = p_document_id
  for update;

  if not found then
    raise exception 'pipeline_job_not_found';
  end if;
  if v_job.status <> 'processing'
    or v_job.locked_by is distinct from p_worker_id
    or v_job.lease_expires_at is null
    or v_job.lease_expires_at <= now() then
    raise exception 'stale_pipeline_worker_lease';
  end if;

  select greatest(1, coalesce(d.max_retry_attempts, 1))
  into v_max_retries
  from public.documents d
  where d.id = p_document_id;

  if v_job.attempts >= v_max_retries then
    update public.document_pipeline_jobs
    set status = 'failed',
        locked_at = null,
        lease_expires_at = null,
        locked_by = null,
        last_error = left(coalesce(p_error, 'pipeline_retry_limit_exhausted'), 2000),
        updated_at = now()
    where id = p_job_id;

    update public.documents
    set processing_status = 'failed',
        retry_attempts = v_job.attempts,
        next_retry_at = null,
        last_error_at = now()
    where id = p_document_id;
    return;
  end if;

  v_retry_at := greatest(coalesce(p_available_at, now()), now());
  update public.document_pipeline_jobs
  set status = 'queued',
      available_at = v_retry_at,
      locked_at = null,
      lease_expires_at = null,
      locked_by = null,
      last_error = left(coalesce(p_error, 'transient_pipeline_failure'), 2000),
      updated_at = now()
  where id = p_job_id;

  update public.documents
  set processing_status = 'pipeline_processing',
      retry_attempts = v_job.attempts,
      next_retry_at = v_retry_at,
      last_error_at = now()
  where id = p_document_id;
end;
$$;

create or replace function public.claim_document_pipeline_job(
  p_worker_id text default gen_random_uuid()::text,
  p_lease_seconds integer default 300
)
returns setof public.document_pipeline_jobs
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  r public.document_pipeline_jobs;
begin
  with exhausted as (
    update public.document_pipeline_jobs j
    set status = 'failed',
        locked_at = null,
        lease_expires_at = null,
        locked_by = null,
        last_error = coalesce(last_error, 'pipeline_retry_limit_exhausted'),
        updated_at = now()
    from public.documents d
    where d.id = j.document_id
      and j.status = 'processing'
      and j.lease_expires_at is not null
      and j.lease_expires_at < now()
      and j.attempts >= greatest(1, coalesce(d.max_retry_attempts, 1))
    returning j.document_id, j.attempts
  )
  update public.documents d
  set processing_status = 'failed',
      retry_attempts = e.attempts,
      next_retry_at = null,
      last_error_at = now()
  from exhausted e
  where d.id = e.document_id;

  update public.document_pipeline_jobs j
  set status = 'queued',
      available_at = now(),
      locked_at = null,
      lease_expires_at = null,
      locked_by = null,
      last_error = coalesce(last_error, 'pipeline_worker_lease_expired'),
      updated_at = now()
  from public.documents d
  where d.id = j.document_id
    and j.status = 'processing'
    and j.lease_expires_at is not null
    and j.lease_expires_at < now()
    and j.attempts < greatest(1, coalesce(d.max_retry_attempts, 1));

  select j.* into r
  from public.document_pipeline_jobs j
  join public.documents d on d.id = j.document_id
  where j.status = 'queued'
    and j.available_at <= now()
    and j.attempts < greatest(1, coalesce(d.max_retry_attempts, 1))
    and not d.manual_review_required
    and d.processing_status <> 'manual_review'
    and (
      (
        j.stage = 'chunk'
        and exists (
          select 1
          from public.document_ocr_jobs o
          where o.document_id = j.document_id
            and o.status = 'completed'
        )
        and exists (
          select 1 from public.document_pages p where p.document_id = j.document_id
        )
        and not exists (
          select 1
          from public.document_pages p
          where p.document_id = j.document_id
            and p.status <> 'completed'
        )
      )
      or (
        j.stage = 'embed'
        and exists (
          select 1
          from public.document_pipeline_jobs p
          where p.document_id = j.document_id
            and p.stage = 'chunk'
            and p.status = 'completed'
        )
        and exists (
          select 1 from public.document_chunks c where c.document_id = j.document_id
        )
      )
      or (
        j.stage = 'analyze'
        and exists (
          select 1
          from public.document_pipeline_jobs p
          where p.document_id = j.document_id
            and p.stage = 'chunk'
            and p.status = 'completed'
        )
        and exists (
          select 1
          from public.document_pipeline_jobs p
          where p.document_id = j.document_id
            and p.stage = 'embed'
            and p.status = 'completed'
        )
        and exists (
          select 1 from public.document_chunks c where c.document_id = j.document_id
        )
        and not exists (
          select 1
          from public.document_chunks c
          where c.document_id = j.document_id
            and c.embedding is null
        )
      )
    )
  order by case j.stage when 'chunk' then 1 when 'embed' then 2 else 3 end,
           j.created_at
  for update of j skip locked
  limit 1;

  if not found then
    return;
  end if;

  update public.document_pipeline_jobs
  set status = 'processing',
      locked_at = now(),
      lease_expires_at = now() + make_interval(secs => greatest(30, p_lease_seconds)),
      locked_by = p_worker_id,
      attempts = attempts + 1,
      updated_at = now()
  where id = r.id
  returning * into r;

  update public.documents
  set processing_status = 'pipeline_processing',
      retry_attempts = r.attempts,
      next_retry_at = null
  where id = r.document_id
    and processing_status <> 'completed';

  return next r;
end;
$$;

revoke all on function public.retry_document_pipeline_job(bigint, uuid, text, text, timestamptz)
  from public, anon, authenticated;
revoke all on function public.claim_document_pipeline_job(text, integer)
  from public, anon, authenticated;

grant execute on function public.retry_document_pipeline_job(bigint, uuid, text, text, timestamptz)
  to service_role;
grant execute on function public.claim_document_pipeline_job(text, integer)
  to service_role;
