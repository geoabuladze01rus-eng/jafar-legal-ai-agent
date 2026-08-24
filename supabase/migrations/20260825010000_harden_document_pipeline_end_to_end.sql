-- Harden the OCR -> chunk -> embed -> analyze pipeline without removing legacy
-- document states that existing clients may still emit.

alter table public.documents
  drop constraint if exists documents_processing_status_check;

alter table public.documents
  add constraint documents_processing_status_check
  check (processing_status = any (array[
    'stored'::text,
    'processing'::text,
    'queued'::text,
    'ocr_processing'::text,
    'ocr_completed'::text,
    'chunking'::text,
    'pipeline_processing'::text,
    'completed'::text,
    'manual_review'::text,
    'failed'::text
  ])) not valid;

alter table public.documents
  validate constraint documents_processing_status_check;

alter table public.document_ocr_jobs
  add column if not exists locked_by text;

alter table public.document_pipeline_jobs
  add column if not exists locked_by text;

alter table public.document_pipeline_jobs
  drop constraint if exists document_pipeline_jobs_attempts_check;

alter table public.document_pipeline_jobs
  add constraint document_pipeline_jobs_attempts_check
  check (attempts >= 0) not valid;

alter table public.document_pipeline_jobs
  validate constraint document_pipeline_jobs_attempts_check;

create or replace function public.enqueue_document_pipeline(p_document_id uuid)
returns integer
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_changed integer := 0;
begin
  perform 1
  from public.documents d
  where d.id = p_document_id
    and not d.manual_review_required
    and d.processing_status <> 'manual_review'
  for update;

  if not found then
    raise exception 'document_not_found_or_manual_review';
  end if;

  if not exists (
    select 1
    from public.document_pages p
    where p.document_id = p_document_id
  ) or exists (
    select 1
    from public.document_pages p
    where p.document_id = p_document_id
      and p.status <> 'completed'
  ) then
    raise exception 'document_pages_not_ready';
  end if;

  insert into public.document_pipeline_jobs (document_id, stage)
  values
    (p_document_id, 'chunk'),
    (p_document_id, 'embed'),
    (p_document_id, 'analyze')
  on conflict (document_id, stage) do update
    set status = 'queued',
        attempts = 0,
        available_at = now(),
        locked_at = null,
        lease_expires_at = null,
        locked_by = null,
        last_error = null,
        updated_at = now()
  where document_pipeline_jobs.status in ('failed', 'manual_review');

  get diagnostics v_changed = row_count;

  if v_changed > 0 or exists (
    select 1
    from public.document_pipeline_jobs j
    where j.document_id = p_document_id
      and j.status <> 'completed'
  ) then
    update public.documents
    set processing_status = 'pipeline_processing',
        manual_review_required = false,
        next_retry_at = null
    where id = p_document_id;
  end if;

  return v_changed;
end;
$$;

create or replace function public.complete_ocr_and_enqueue_pipeline(
  p_job_id bigint,
  p_document_id uuid,
  p_pages_total integer,
  p_pages_completed integer,
  p_manual_review boolean,
  p_worker_id text
)
returns void
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_job public.document_ocr_jobs;
  v_actual_pages integer;
  v_bad_pages integer;
  v_manual_review boolean;
begin
  select * into v_job
  from public.document_ocr_jobs j
  where j.id = p_job_id
    and j.document_id = p_document_id
  for update;

  if not found then
    raise exception 'ocr_job_not_found';
  end if;

  -- A terminal completion is immutable. Repeating a successful completion may
  -- heal missing queue rows, while unique(document_id, stage) prevents duplicates.
  if v_job.status = 'completed' then
    perform public.enqueue_document_pipeline(p_document_id);
    return;
  elsif v_job.status = 'manual_review' then
    return;
  end if;

  if v_job.status <> 'processing' then
    raise exception 'ocr_job_not_processing';
  end if;
  if p_worker_id is not null and (
    v_job.locked_by is distinct from p_worker_id
    or v_job.lease_expires_at is null
    or v_job.lease_expires_at <= now()
  ) then
    raise exception 'stale_ocr_worker_lease';
  end if;

  perform 1
  from public.documents d
  where d.id = p_document_id
  for update;
  if not found then
    raise exception 'document_not_found';
  end if;

  select count(*), count(*) filter (where p.status <> 'completed')
  into v_actual_pages, v_bad_pages
  from public.document_pages p
  where p.document_id = p_document_id;

  v_manual_review := coalesce(p_manual_review, false)
    or coalesce(p_pages_total, 0) <= 0
    or coalesce(p_pages_completed, 0) <> coalesce(p_pages_total, 0)
    or v_actual_pages <> coalesce(p_pages_completed, 0)
    or v_bad_pages > 0;

  update public.document_ocr_jobs
  set status = case when v_manual_review then 'manual_review' else 'completed' end,
      pages_total = greatest(coalesce(p_pages_total, 0), 0),
      pages_completed = greatest(coalesce(p_pages_completed, 0), 0),
      finished_at = now(),
      last_error = case
        when v_manual_review then coalesce(last_error, 'ocr_manual_review_required')
        else null
      end,
      locked_at = null,
      lease_expires_at = null,
      locked_by = null,
      updated_at = now()
  where id = p_job_id;

  if v_manual_review then
    update public.documents
    set processing_status = 'manual_review',
        manual_review_required = true,
        retry_attempts = v_job.attempts,
        next_retry_at = null,
        last_error_at = now()
    where id = p_document_id;
    return;
  end if;

  update public.documents
  set processing_status = 'ocr_completed',
      manual_review_required = false,
      retry_attempts = v_job.attempts,
      next_retry_at = null
  where id = p_document_id;

  perform public.enqueue_document_pipeline(p_document_id);
end;
$$;

-- Compatibility wrapper for a rolling deployment. New workers always use the
-- six-argument overload so lease fencing remains enforced.
create or replace function public.complete_ocr_and_enqueue_pipeline(
  p_job_id bigint,
  p_document_id uuid,
  p_pages_total integer,
  p_pages_completed integer,
  p_manual_review boolean default false
)
returns void
language sql
security definer
set search_path = public, pg_catalog
as $$
  select public.complete_ocr_and_enqueue_pipeline(
    p_job_id,
    p_document_id,
    p_pages_total,
    p_pages_completed,
    p_manual_review,
    null
  );
$$;

create or replace function public.fail_document_ocr_job(
  p_job_id bigint,
  p_document_id uuid,
  p_worker_id text,
  p_error text,
  p_retry boolean,
  p_available_at timestamptz default null
)
returns text
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_job public.document_ocr_jobs;
  v_max_retries integer;
  v_terminal boolean;
begin
  select j.* into v_job
  from public.document_ocr_jobs j
  where j.id = p_job_id
    and j.document_id = p_document_id
  for update;

  if not found then
    raise exception 'ocr_job_not_found';
  end if;
  if v_job.status <> 'processing'
    or v_job.locked_by is distinct from p_worker_id
    or v_job.lease_expires_at is null
    or v_job.lease_expires_at <= now() then
    raise exception 'stale_ocr_worker_lease';
  end if;

  select d.max_retry_attempts into v_max_retries
  from public.documents d
  where d.id = p_document_id
  for update;
  if not found then
    raise exception 'document_not_found';
  end if;

  v_terminal := not coalesce(p_retry, false) or v_job.attempts >= v_max_retries;

  update public.document_ocr_jobs
  set status = case when v_terminal then 'manual_review' else 'queued' end,
      last_error = left(coalesce(p_error, 'ocr_failed'), 2000),
      finished_at = case when v_terminal then now() else null end,
      available_at = case
        when v_terminal then now()
        else greatest(coalesce(p_available_at, now()), now())
      end,
      locked_at = null,
      lease_expires_at = null,
      locked_by = null,
      updated_at = now()
  where id = p_job_id;

  update public.documents
  set processing_status = case when v_terminal then 'manual_review' else 'queued' end,
      manual_review_required = v_terminal,
      retry_attempts = v_job.attempts,
      last_error_at = now(),
      next_retry_at = case when v_terminal then null else greatest(coalesce(p_available_at, now()), now()) end
  where id = p_document_id;

  return case when v_terminal then 'manual_review' else 'queued' end;
end;
$$;

create or replace function public.claim_document_ocr_job(
  p_worker_id text default gen_random_uuid()::text,
  p_lease_seconds integer default 300
)
returns setof public.document_ocr_jobs
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  r public.document_ocr_jobs;
begin
  -- Exhausted abandoned/queued jobs are terminal and cannot spin forever.
  update public.document_ocr_jobs j
  set status = 'manual_review',
      finished_at = coalesce(j.finished_at, now()),
      locked_at = null,
      lease_expires_at = null,
      locked_by = null,
      last_error = coalesce(j.last_error, 'ocr_retry_limit_exhausted'),
      updated_at = now()
  from public.documents d
  where d.id = j.document_id
    and j.status in ('queued', 'processing')
    and j.attempts >= d.max_retry_attempts
    and (j.status = 'queued' or j.lease_expires_at < now());

  update public.documents d
  set processing_status = 'manual_review',
      manual_review_required = true,
      next_retry_at = null,
      last_error_at = coalesce(d.last_error_at, now())
  where exists (
    select 1
    from public.document_ocr_jobs j
    where j.document_id = d.id
      and j.status = 'manual_review'
  );

  update public.document_ocr_jobs
  set status = 'queued',
      available_at = now(),
      locked_at = null,
      lease_expires_at = null,
      locked_by = null,
      last_error = coalesce(last_error, 'ocr_worker_lease_expired'),
      updated_at = now()
  where status = 'processing'
    and lease_expires_at is not null
    and lease_expires_at < now();

  select j.* into r
  from public.document_ocr_jobs j
  join public.documents d on d.id = j.document_id
  where j.status = 'queued'
    and j.available_at <= now()
    and j.attempts < d.max_retry_attempts
    and not d.manual_review_required
    and d.processing_status <> 'manual_review'
  order by j.created_at
  for update of j skip locked
  limit 1;

  if not found then
    return;
  end if;

  update public.document_ocr_jobs
  set status = 'processing',
      attempts = attempts + 1,
      locked_at = now(),
      lease_expires_at = now() + make_interval(secs => greatest(30, p_lease_seconds)),
      locked_by = p_worker_id,
      started_at = coalesce(started_at, now()),
      finished_at = null,
      updated_at = now()
  where id = r.id
  returning * into r;

  update public.documents
  set processing_status = 'ocr_processing',
      manual_review_required = false,
      retry_attempts = r.attempts,
      next_retry_at = null
  where id = r.document_id;

  return next r;
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
  update public.document_pipeline_jobs
  set status = 'queued',
      available_at = now(),
      locked_at = null,
      lease_expires_at = null,
      locked_by = null,
      last_error = coalesce(last_error, 'pipeline_worker_lease_expired'),
      updated_at = now()
  where status = 'processing'
    and lease_expires_at is not null
    and lease_expires_at < now();

  select j.* into r
  from public.document_pipeline_jobs j
  join public.documents d on d.id = j.document_id
  where j.status = 'queued'
    and j.available_at <= now()
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
  set processing_status = 'pipeline_processing'
  where id = r.document_id
    and processing_status <> 'completed';

  return next r;
end;
$$;

create or replace function public.finish_document_pipeline_job(
  p_job_id bigint,
  p_document_id uuid,
  p_worker_id text,
  p_status text,
  p_error text default null
)
returns void
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  v_job public.document_pipeline_jobs;
begin
  if p_status not in ('queued', 'completed', 'failed', 'manual_review') then
    raise exception 'invalid_pipeline_finish_status';
  end if;

  select * into v_job
  from public.document_pipeline_jobs j
  where j.id = p_job_id
    and j.document_id = p_document_id
  for update;

  if not found then
    raise exception 'pipeline_job_not_found';
  end if;
  if v_job.status = 'completed' and p_status = 'completed' then
    return;
  end if;
  if v_job.status <> 'processing'
    or v_job.locked_by is distinct from p_worker_id
    or v_job.lease_expires_at is null
    or v_job.lease_expires_at <= now() then
    raise exception 'stale_pipeline_worker_lease';
  end if;

  if p_status = 'completed' and v_job.stage = 'chunk' and not exists (
    select 1 from public.document_chunks c where c.document_id = p_document_id
  ) then
    raise exception 'chunk_stage_incomplete';
  elsif p_status = 'completed' and v_job.stage = 'embed' and (
    not exists (
      select 1 from public.document_chunks c where c.document_id = p_document_id
    )
    or exists (
      select 1
      from public.document_chunks c
      where c.document_id = p_document_id
        and c.embedding is null
    )
  ) then
    raise exception 'embedding_stage_incomplete';
  elsif p_status = 'completed' and v_job.stage = 'analyze' and not exists (
    select 1
    from public.ai_analyses a
    join public.documents d on d.id = a.document_id
    where a.document_id = p_document_id
      and a.matter_id = d.matter_id
      and a.analysis_type = 'document_pipeline'
      and a.status = 'completed'
      and a.requires_lawyer_review
      and jsonb_typeof(a.citations) = 'array'
      and a.citations <> '[]'::jsonb
      and jsonb_typeof(a.source_chunks) = 'array'
      and a.source_chunks <> '[]'::jsonb
  ) then
    raise exception 'analysis_stage_incomplete_or_ungrounded';
  end if;

  update public.document_pipeline_jobs
  set status = p_status,
      available_at = case when p_status = 'queued' then now() else available_at end,
      locked_at = null,
      lease_expires_at = null,
      locked_by = null,
      last_error = case
        when p_status in ('failed', 'manual_review') then left(coalesce(p_error, p_status), 2000)
        else null
      end,
      updated_at = now()
  where id = p_job_id;

  if p_status = 'manual_review' then
    update public.documents
    set processing_status = 'manual_review',
        manual_review_required = true,
        last_error_at = now()
    where id = p_document_id;
  elsif p_status = 'failed' then
    update public.documents
    set processing_status = 'failed',
        last_error_at = now()
    where id = p_document_id;
  elsif p_status = 'completed'
    and v_job.stage = 'analyze'
    and not exists (
      select 1
      from public.document_pipeline_jobs j
      where j.document_id = p_document_id
        and j.status <> 'completed'
    ) then
    update public.documents
    set processing_status = 'completed',
        manual_review_required = false,
        next_retry_at = null
    where id = p_document_id;
  else
    update public.documents
    set processing_status = 'pipeline_processing'
    where id = p_document_id;
  end if;
end;
$$;

revoke all on function public.enqueue_document_pipeline(uuid) from public, anon, authenticated;
revoke all on function public.complete_ocr_and_enqueue_pipeline(bigint, uuid, integer, integer, boolean) from public, anon, authenticated;
revoke all on function public.complete_ocr_and_enqueue_pipeline(bigint, uuid, integer, integer, boolean, text) from public, anon, authenticated;
revoke all on function public.fail_document_ocr_job(bigint, uuid, text, text, boolean, timestamptz) from public, anon, authenticated;
revoke all on function public.claim_document_ocr_job(text, integer) from public, anon, authenticated;
revoke all on function public.claim_document_pipeline_job(text, integer) from public, anon, authenticated;
revoke all on function public.finish_document_pipeline_job(bigint, uuid, text, text, text) from public, anon, authenticated;

grant execute on function public.enqueue_document_pipeline(uuid) to service_role;
grant execute on function public.complete_ocr_and_enqueue_pipeline(bigint, uuid, integer, integer, boolean) to service_role;
grant execute on function public.complete_ocr_and_enqueue_pipeline(bigint, uuid, integer, integer, boolean, text) to service_role;
grant execute on function public.fail_document_ocr_job(bigint, uuid, text, text, boolean, timestamptz) to service_role;
grant execute on function public.claim_document_ocr_job(text, integer) to service_role;
grant execute on function public.claim_document_pipeline_job(text, integer) to service_role;
grant execute on function public.finish_document_pipeline_job(bigint, uuid, text, text, text) to service_role;
