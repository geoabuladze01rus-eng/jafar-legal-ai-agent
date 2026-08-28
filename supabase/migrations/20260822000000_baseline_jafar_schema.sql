SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET row_security = off;

-- Name: pg_cron; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_cron WITH SCHEMA pg_catalog;


--

-- Name: pg_net; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_net WITH SCHEMA public;


--

-- Name: pg_stat_statements; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_stat_statements WITH SCHEMA extensions;


--

-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;


--

-- Name: supabase_vault; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS supabase_vault WITH SCHEMA vault;


--

-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA extensions;


--

-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;


--

-- Name: document_ocr_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_ocr_jobs (
    id bigint NOT NULL,
    document_id uuid NOT NULL,
    status text DEFAULT 'queued'::text NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    available_at timestamp with time zone DEFAULT now() NOT NULL,
    locked_at timestamp with time zone,
    lease_expires_at timestamp with time zone,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    last_error text,
    ocr_provider text,
    pages_total integer,
    pages_completed integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT document_ocr_jobs_attempts_check CHECK ((attempts >= 0)),
    CONSTRAINT document_ocr_jobs_pages_completed_check CHECK ((pages_completed >= 0)),
    CONSTRAINT document_ocr_jobs_pages_total_check CHECK (((pages_total IS NULL) OR (pages_total >= 0))),
    CONSTRAINT document_ocr_jobs_status_check CHECK ((status = ANY (ARRAY['queued'::text, 'processing'::text, 'completed'::text, 'failed'::text, 'manual_review'::text])))
);


--

-- Name: claim_document_ocr_job(text, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.claim_document_ocr_job(p_worker_id text DEFAULT (gen_random_uuid())::text, p_lease_seconds integer DEFAULT 300) RETURNS SETOF public.document_ocr_jobs
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
declare
  r public.document_ocr_jobs;
begin
  update public.document_ocr_jobs
     set status = 'queued',
         locked_at = null,
         lease_expires_at = null
   where status = 'processing'
     and lease_expires_at is not null
     and lease_expires_at < now();

  select * into r
    from public.document_ocr_jobs
   where status = 'queued'
     and (available_at is null or available_at <= now())
   order by created_at
   for update skip locked
   limit 1;

  if not found then
    return;
  end if;

  update public.document_ocr_jobs
     set status = 'processing',
         locked_at = now(),
         lease_expires_at = now() + make_interval(secs => greatest(30, p_lease_seconds)),
         started_at = coalesce(started_at, now()),
         updated_at = now()
   where id = r.id
   returning * into r;

  return next r;
end;
$$;


--

-- Name: claim_document_ocr_job_for_owner(text, text, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.claim_document_ocr_job_for_owner(p_owner_user_id text, p_worker_id text DEFAULT (gen_random_uuid())::text, p_lease_seconds integer DEFAULT 300) RETURNS SETOF public.document_ocr_jobs
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
declare r public.document_ocr_jobs;
begin
  update public.document_ocr_jobs j
  set status='queued', locked_at=null, lease_expires_at=null, updated_at=now()
  from public.documents d join public.matters m on m.id=d.matter_id
  where j.document_id=d.id and m.owner_user_id=p_owner_user_id and j.status='processing' and j.lease_expires_at is not null and j.lease_expires_at < now();
  select j.* into r from public.document_ocr_jobs j join public.documents d on d.id=j.document_id join public.matters m on m.id=d.matter_id
  where m.owner_user_id=p_owner_user_id and j.status='queued' and (j.available_at is null or j.available_at <= now())
  order by j.created_at for update of j skip locked limit 1;
  if not found then return; end if;
  update public.document_ocr_jobs set status='processing', locked_at=now(), lease_expires_at=now()+make_interval(secs=>greatest(30,p_lease_seconds)), started_at=coalesce(started_at,now()), attempts=attempts+1, updated_at=now(), ocr_provider='openai' where id=r.id returning * into r;
  return next r;
end; $$;


--

-- Name: document_pipeline_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_pipeline_jobs (
    id bigint NOT NULL,
    document_id uuid NOT NULL,
    stage text NOT NULL,
    status text DEFAULT 'queued'::text NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    available_at timestamp with time zone DEFAULT now() NOT NULL,
    locked_at timestamp with time zone,
    lease_expires_at timestamp with time zone,
    last_error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT document_pipeline_jobs_stage_check CHECK ((stage = ANY (ARRAY['chunk'::text, 'embed'::text, 'analyze'::text]))),
    CONSTRAINT document_pipeline_jobs_status_check CHECK ((status = ANY (ARRAY['queued'::text, 'processing'::text, 'completed'::text, 'failed'::text, 'manual_review'::text])))
);


--

-- Name: claim_document_pipeline_job(text, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.claim_document_pipeline_job(p_worker_id text DEFAULT (gen_random_uuid())::text, p_lease_seconds integer DEFAULT 300) RETURNS SETOF public.document_pipeline_jobs
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
declare
  r public.document_pipeline_jobs;
begin
  update public.document_pipeline_jobs
     set status='queued', locked_at=null, lease_expires_at=null
   where status='processing'
     and lease_expires_at is not null
     and lease_expires_at < now();

  select j.* into r
    from public.document_pipeline_jobs j
   where j.status='queued'
     and (j.available_at is null or j.available_at <= now())
     and (
       j.stage='chunk'
       or (
         j.stage='embed'
         and not exists (
           select 1 from public.document_pipeline_jobs p
            where p.document_id=j.document_id and p.stage='chunk'
              and p.status <> 'completed'
         )
         and exists (
           select 1 from public.document_chunks c where c.document_id=j.document_id
         )
       )
       or (
         j.stage='analyze'
         and not exists (
           select 1 from public.document_pipeline_jobs p
            where p.document_id=j.document_id and p.stage in ('chunk','embed')
              and p.status <> 'completed'
         )
         and exists (
           select 1 from public.document_chunks c
            where c.document_id=j.document_id
              and c.embedding is not null
         )
       )
     )
   order by case j.stage when 'chunk' then 1 when 'embed' then 2 else 3 end, j.created_at
   for update skip locked
   limit 1;

  if not found then return; end if;

  update public.document_pipeline_jobs
     set status='processing',
         locked_at=now(),
         lease_expires_at=now()+make_interval(secs=>greatest(30,p_lease_seconds)),
         attempts=attempts+1,
         updated_at=now()
   where id=r.id
   returning * into r;

  return next r;
end;
$$;


--

-- Name: claim_document_recovery_jobs(text, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.claim_document_recovery_jobs(p_worker_id text, p_limit integer DEFAULT 5) RETURNS TABLE(id uuid, storage_path text, attempts integer)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
begin
 return query
 with picked as (
  select j.id from public.document_recovery_jobs j
  where j.status='queued' and j.available_at<=now()
  order by j.available_at,j.created_at
  for update skip locked
  limit greatest(1,least(p_limit,50))
 )
 update public.document_recovery_jobs j
 set status='processing', attempts=j.attempts+1, locked_at=now(),
     lease_expires_at=now()+interval '5 minutes', locked_by=p_worker_id, updated_at=now()
 from picked p where j.id=p.id
 returning j.id,j.storage_path,j.attempts;
end;
$$;


--

-- Name: claim_due_failed_documents(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.claim_due_failed_documents(p_limit integer DEFAULT 10) RETURNS TABLE(storage_path text, retry_attempts integer)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
begin
 return query
 with candidates as (
  select d.ctid from public.documents d
   where d.processing_status='failed' and d.manual_review_required=false
     and d.retry_attempts < d.max_retry_attempts
     and (d.next_retry_at is null or d.next_retry_at <= now())
   order by coalesce(d.next_retry_at,d.last_error_at,now()),d.ctid
   for update skip locked limit greatest(1,least(p_limit,100))
 ), claimed as (
  update public.documents d set processing_status='processing',processing_error=null,
   retry_attempts=d.retry_attempts+1,last_error_at=null,next_retry_at=null
   from candidates c where d.ctid=c.ctid
   returning d.storage_path,d.retry_attempts
 ) select * from claimed;
end;
$$;


--

-- Name: telegram_publications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.telegram_publications (
    id bigint NOT NULL,
    telegram_message_id bigint,
    chat_id text NOT NULL,
    title text,
    body text NOT NULL,
    status text DEFAULT 'draft'::text NOT NULL,
    scheduled_at timestamp with time zone,
    published_at timestamp with time zone,
    metrics jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    claimed_at timestamp with time zone,
    claim_token uuid
);


--

-- Name: claim_due_telegram_publications(timestamp with time zone, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.claim_due_telegram_publications(p_now timestamp with time zone, p_limit integer DEFAULT 10) RETURNS SETOF public.telegram_publications
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
begin
  return query
  with candidates as (
    select id
    from public.telegram_publications
    where status = 'approved'
      and scheduled_at is not null
      and scheduled_at <= p_now
      and claimed_at is null
    order by scheduled_at, id
    for update skip locked
    limit greatest(1, least(p_limit, 50))
  )
  update public.telegram_publications p
  set claimed_at = p_now,
      claim_token = gen_random_uuid()
  from candidates c
  where p.id = c.id
  returning p.*;
end;
$$;


--

-- Name: claim_email_processing(text, text, text, timestamp with time zone); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.claim_email_processing(p_message_id text, p_sender text, p_subject text, p_received_at timestamp with time zone) RETURNS boolean
    LANGUAGE plpgsql
    SET search_path TO 'public'
    AS $$
declare
  claimed boolean;
begin
  insert into public.emails (message_id, sender, subject, received_at, processing_status)
  values (p_message_id, p_sender, p_subject, p_received_at, 'claimed')
  on conflict (message_id) do update
    set processing_status = 'claimed',
        sender = excluded.sender,
        subject = excluded.subject,
        received_at = excluded.received_at
    where public.emails.processing_status = 'failed';

  get diagnostics claimed = row_count;
  return claimed;
end;
$$;


--

-- Name: claim_failed_document_for_retry(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.claim_failed_document_for_retry(p_storage_path text) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
declare v_updated integer;
begin
  update public.documents
     set processing_status='processing', processing_error=null,
         retry_attempts=retry_attempts+1, last_error_at=null, next_retry_at=null
   where storage_path=p_storage_path and processing_status='failed'
     and manual_review_required=false
     and retry_attempts < max_retry_attempts
     and (next_retry_at is null or next_retry_at <= now());
  get diagnostics v_updated=row_count;
  return v_updated=1;
end;
$$;


--

-- Name: complete_email_processing(text, boolean); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.complete_email_processing(p_message_id text, p_failed boolean DEFAULT false) RETURNS boolean
    LANGUAGE plpgsql
    SET search_path TO 'public'
    AS $$
begin
  update public.emails
     set processing_status = case when p_failed then 'failed' else 'processed' end
   where message_id = p_message_id;
  return found;
end;
$$;


--

-- Name: complete_ocr_and_enqueue_pipeline(bigint, uuid, integer, integer, boolean); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.complete_ocr_and_enqueue_pipeline(p_job_id bigint, p_document_id uuid, p_pages_total integer, p_pages_completed integer, p_manual_review boolean DEFAULT false) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
begin
  update public.document_ocr_jobs set status=case when p_manual_review then 'manual_review' else 'completed' end, pages_total=p_pages_total, pages_completed=p_pages_completed, finished_at=now(), updated_at=now() where id=p_job_id and document_id=p_document_id;
  update public.documents set processing_status=case when p_manual_review then 'manual_review' else 'chunking' end, manual_review_required=p_manual_review where id=p_document_id;
  if not p_manual_review then perform public.enqueue_document_pipeline(p_document_id); end if;
end; $$;


--

-- Name: detect_recovery_worker_incident(interval); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.detect_recovery_worker_incident(p_stale_after interval DEFAULT '00:15:00'::interval) RETURNS TABLE(incident_id bigint, incident_type text, severity text, details text)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
declare
  v_last_completed timestamptz;
  v_last_started timestamptz;
  v_last_status text;
  v_incident_id bigint;
begin
  select max(finished_at) filter (where status='completed'), max(started_at),
         (array_agg(status order by started_at desc))[1]
    into v_last_completed, v_last_started, v_last_status
    from public.recovery_worker_runs;

  if v_last_completed is null or v_last_completed < now() - p_stale_after then
    insert into public.recovery_worker_incidents(incident_type,severity,details)
    select 'worker_stale','critical','No successful recovery worker run within ' || p_stale_after
    where not exists (
      select 1 from public.recovery_worker_incidents
       where incident_type='worker_stale' and resolved_at is null
    )
    returning id into v_incident_id;

    if v_incident_id is not null then
      return query select v_incident_id,'worker_stale','critical','No successful recovery worker run within ' || p_stale_after;
      return;
    end if;
  end if;

  if v_last_status='failed' then
    insert into public.recovery_worker_incidents(incident_type,severity,details)
    select 'worker_failed','warning','Latest recovery worker run failed'
    where not exists (
      select 1 from public.recovery_worker_incidents
       where incident_type='worker_failed' and detected_at > now() - interval '15 minutes' and resolved_at is null
    )
    returning id into v_incident_id;
    if v_incident_id is not null then
      return query select v_incident_id,'worker_failed','warning','Latest recovery worker run failed';
      return;
    end if;
  end if;

  return;
end;
$$;


--

-- Name: enqueue_document_ocr_job(uuid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.enqueue_document_ocr_job(p_document_id uuid) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
declare v_id uuid;
begin
  insert into public.document_ocr_jobs(document_id,status,created_at) values(p_document_id,'queued',now()) on conflict (document_id) where status in ('queued','processing','manual_review') do nothing returning id into v_id;
  return v_id;
end; $$;


--

-- Name: enqueue_document_pipeline(uuid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.enqueue_document_pipeline(p_document_id uuid) RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
declare n integer;
begin
  insert into public.document_pipeline_jobs(document_id,stage) values (p_document_id,'chunk'),(p_document_id,'embed'),(p_document_id,'analyze') on conflict(document_id,stage) do nothing;
  get diagnostics n = row_count;
  return n;
end; $$;


--

-- Name: enqueue_due_document_recovery(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.enqueue_due_document_recovery(p_limit integer DEFAULT 10) RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
declare v_count integer;
begin
  insert into public.document_recovery_jobs(storage_path, available_at)
  select d.storage_path, coalesce(d.next_retry_at, now())
  from public.documents d
  where d.processing_status='failed'
    and d.manual_review_required=false
    and d.retry_attempts < d.max_retry_attempts
    and (d.next_retry_at is null or d.next_retry_at <= now())
    and not exists (
      select 1 from public.document_recovery_jobs j
      where j.storage_path=d.storage_path and j.status in ('queued','processing')
    )
  order by coalesce(d.next_retry_at, d.last_error_at, now())
  limit greatest(1, least(p_limit, 100))
  on conflict do nothing;
  get diagnostics v_count=row_count;
  return v_count;
end;
$$;


--

-- Name: finish_document_recovery_job(uuid, text, boolean, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.finish_document_recovery_job(p_id uuid, p_worker_id text, p_success boolean, p_error text DEFAULT NULL::text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
begin
  update public.document_recovery_jobs
  set status=case when p_success then 'completed' else 'failed' end,
      last_error=case when p_success then null else p_error end,
      lease_expires_at=null,
      locked_at=null,
      locked_by=null,
      updated_at=now()
  where id=p_id and status='processing' and locked_by=p_worker_id
    and (lease_expires_at is null or lease_expires_at >= now());
  if not found then
    raise exception 'recovery job lease is invalid or expired: %', p_id;
  end if;
end;
$$;


--

-- Name: finish_document_retry(text, boolean, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.finish_document_retry(p_storage_path text, p_success boolean, p_error text DEFAULT NULL::text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
declare v_attempts integer; v_max integer;
begin
  select retry_attempts,max_retry_attempts into v_attempts,v_max from public.documents
   where storage_path=p_storage_path and processing_status='processing' for update;
  if not found then raise exception 'document retry is not in processing state: %',p_storage_path; end if;
  update public.documents
     set processing_status=case when p_success then 'completed' else 'failed' end,
         processing_error=case when p_success then null else p_error end,
         last_error_at=case when p_success then null else now() end,
         next_retry_at=case when p_success or v_attempts>=v_max then null else now() + make_interval(secs => least(21600, 60 * (2 ^ greatest(v_attempts-1,0)))) end,
         manual_review_required=case when p_success then false else v_attempts>=v_max end
   where storage_path=p_storage_path;
end;
$$;


--

-- Name: finish_document_retry(text, boolean, text, timestamp with time zone); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.finish_document_retry(p_storage_path text, p_success boolean, p_error text DEFAULT NULL::text, p_next_retry_at timestamp with time zone DEFAULT NULL::timestamp with time zone) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
begin
  update public.documents
     set processing_status = case when p_success then 'completed' else 'failed' end,
         processing_error = case when p_success then null else p_error end,
         last_error_at = case when p_success then null else now() end,
         next_retry_at = case when p_success then null else p_next_retry_at end
   where storage_path = p_storage_path
     and processing_status = 'processing';
  if not found then
    raise exception 'document retry is not in processing state: %', p_storage_path;
  end if;
end;
$$;


--

-- Name: heartbeat_recovery_job(uuid, text, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.heartbeat_recovery_job(p_id uuid, p_worker_id text, p_lease_seconds integer DEFAULT 300) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
declare v_updated integer;
begin
 update public.document_recovery_jobs
 set locked_at=now(), lease_expires_at=now()+make_interval(secs=>greatest(30,least(p_lease_seconds,3600))), updated_at=now()
 where id=p_id and status='processing' and locked_by=p_worker_id;
 get diagnostics v_updated=row_count;
 return v_updated=1;
end;
$$;


--

-- Name: match_document_chunks(extensions.vector, integer, uuid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.match_document_chunks(query_embedding extensions.vector, match_count integer DEFAULT 8, filter_document_id uuid DEFAULT NULL::uuid) RETURNS TABLE(id uuid, document_id uuid, chunk_index integer, content text, source_page integer, similarity double precision)
    LANGUAGE sql STABLE
    SET search_path TO 'public', 'pg_catalog'
    AS $$
  select dc.id, dc.document_id, dc.chunk_index, dc.content, dc.source_page,
         1 - (dc.embedding <=> query_embedding) as similarity
  from public.document_chunks dc
  where dc.embedding is not null
    and (filter_document_id is null or dc.document_id = filter_document_id)
  order by dc.embedding <=> query_embedding
  limit greatest(match_count, 1);
$$;


--

-- Name: persist_email_processing(jsonb); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.persist_email_processing(p_payload jsonb) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
declare
  v_message_id text := p_payload->>'message_id';
  v_email_id uuid;
  v_doc jsonb;
  v_matter_id uuid;
begin
  if v_message_id is null or v_message_id = '' then raise exception 'message_id is required'; end if;
  select id into v_email_id from public.emails where message_id = v_message_id;
  if v_email_id is null then raise exception 'email not found for message_id %', v_message_id; end if;

  for v_doc in select value from jsonb_array_elements(coalesce(p_payload->'documents','[]'::jsonb)) loop
    v_matter_id := nullif(v_doc->>'matter_id','')::uuid;
    insert into public.documents (
      matter_id, filename, content_type, source, storage_path, ocr_required,
      processing_status, processing_error
    ) values (
      v_matter_id,
      v_doc->>'filename',
      v_doc->>'content_type',
      'email',
      v_doc->>'storage_path',
      coalesce((v_doc->>'ocr_required')::boolean,false),
      coalesce(nullif(v_doc->>'processing_status',''),'stored'),
      nullif(v_doc->>'processing_error','')
    );
  end loop;
end;
$$;


--

-- Name: matter_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.matter_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    matter_id uuid NOT NULL,
    owner_user_id text,
    title text NOT NULL,
    event_date timestamp with time zone NOT NULL,
    description text,
    source_document text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    document_fingerprint text
);


--

-- Name: record_document_event(uuid, text, timestamp with time zone, text, text, text, jsonb); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.record_document_event(p_matter_id uuid, p_title text, p_event_date timestamp with time zone, p_description text DEFAULT NULL::text, p_source_document text DEFAULT NULL::text, p_document_fingerprint text DEFAULT NULL::text, p_deadlines jsonb DEFAULT '[]'::jsonb) RETURNS public.matter_events
    LANGUAGE plpgsql
    SET search_path TO 'public', 'pg_catalog'
    AS $$
declare
  v_event public.matter_events;
  v_owner text;
  v_deadline jsonb;
begin
  select owner_user_id into v_owner
  from public.matters
  where id = p_matter_id
    and owner_user_id = (select auth.uid())::text
  for update;

  if v_owner is null then
    raise exception 'matter_not_found_or_forbidden';
  end if;

  if p_document_fingerprint is not null then
    select * into v_event
    from public.matter_events
    where matter_id = p_matter_id
      and document_fingerprint = p_document_fingerprint;

    if found then
      return v_event;
    end if;
  end if;

  for v_deadline in select * from jsonb_array_elements(coalesce(p_deadlines, '[]'::jsonb)) loop
    insert into public.deadlines (matter_id, owner_user_id, title, due_date, source_text)
    values (
      p_matter_id,
      v_owner,
      v_deadline->>'title',
      (v_deadline->>'due_date')::timestamptz,
      v_deadline->>'source_text'
    );
  end loop;

  insert into public.matter_events (
    matter_id, owner_user_id, title, event_date, description,
    source_document, document_fingerprint
  ) values (
    p_matter_id, v_owner, p_title, p_event_date, p_description,
    p_source_document, p_document_fingerprint
  )
  returning * into v_event;

  update public.matters
  set updated_at = now()
  where id = p_matter_id;

  return v_event;
exception
  when unique_violation then
    select * into v_event
    from public.matter_events
    where matter_id = p_matter_id
      and document_fingerprint = p_document_fingerprint;
    if found then
      return v_event;
    end if;
    raise;
end;
$$;


--

-- Name: record_recovery_worker_run(timestamp with time zone, timestamp with time zone, integer, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.record_recovery_worker_run(p_started_at timestamp with time zone, p_finished_at timestamp with time zone, p_claimed_count integer, p_status text, p_error text DEFAULT NULL::text) RETURNS bigint
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
declare v_id bigint;
begin
  insert into public.recovery_worker_runs(started_at,finished_at,claimed_count,status,error)
  values(p_started_at,p_finished_at,greatest(0,p_claimed_count),p_status,p_error)
  returning id into v_id;
  return v_id;
end;
$$;


--

-- Name: requeue_expired_recovery_jobs(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.requeue_expired_recovery_jobs(p_limit integer DEFAULT 50) RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
declare v_count integer;
begin
 with expired as (
  select id from public.document_recovery_jobs
  where status='processing' and lease_expires_at is not null and lease_expires_at < now()
  order by lease_expires_at
  for update skip locked
  limit greatest(1,least(p_limit,100))
 )
 update public.document_recovery_jobs j
 set status='queued', locked_at=null, lease_expires_at=null, locked_by=null,
     last_error=coalesce(j.last_error,'worker lease expired'), updated_at=now()
 from expired e where j.id=e.id;
 get diagnostics v_count=row_count;
 return v_count;
end;
$$;


--

-- Name: requeue_stale_telegram_publications(timestamp with time zone, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.requeue_stale_telegram_publications(p_now timestamp with time zone, p_lease_seconds integer DEFAULT 300) RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
declare
  affected integer;
begin
  update public.telegram_publications
  set claimed_at = null,
      claim_token = null
  where status = 'approved'
    and claimed_at is not null
    and claimed_at < p_now - make_interval(secs => greatest(30, p_lease_seconds));
  get diagnostics affected = row_count;
  return affected;
end;
$$;


--

-- Name: resolve_recovery_worker_incidents(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.resolve_recovery_worker_incidents() RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
declare v_count integer;
begin
  update public.recovery_worker_incidents i
     set resolved_at = now()
   where i.resolved_at is null
     and exists (
       select 1
       from public.recovery_worker_runs r
       where r.status = 'completed'
         and r.finished_at is not null
         and r.finished_at > i.detected_at
     );
  get diagnostics v_count = row_count;
  return v_count;
end;
$$;


--

-- Name: telegram_comment_queue; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.telegram_comment_queue (
    id bigint NOT NULL,
    telegram_update_id bigint,
    chat_id text,
    message_id bigint,
    author_id bigint,
    text text NOT NULL,
    route text NOT NULL,
    status text DEFAULT 'queued'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    resolved_at timestamp with time zone,
    resolution_note text,
    resolved_by bigint
);


--

-- Name: resolve_telegram_comment(bigint, text, bigint, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.resolve_telegram_comment(p_queue_id bigint, p_status text, p_resolved_by bigint, p_note text DEFAULT NULL::text) RETURNS public.telegram_comment_queue
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
declare
  updated_row public.telegram_comment_queue;
begin
  if p_status not in ('approved','rejected') then
    raise exception 'invalid resolution status';
  end if;

  update public.telegram_comment_queue
  set status = p_status,
      resolved_at = now(),
      resolved_by = p_resolved_by,
      resolution_note = p_note
  where id = p_queue_id
    and status = 'queued'
  returning * into updated_row;

  if not found then
    raise exception 'review item not found or already resolved';
  end if;

  return updated_row;
end;
$$;


--

-- Name: run_document_recovery_tick(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.run_document_recovery_tick(p_limit integer DEFAULT 10) RETURNS TABLE(storage_path text, retry_attempts integer)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
begin
  return query
  with candidates as (
    select d.ctid
    from public.documents d
    where d.processing_status = 'failed'
      and d.manual_review_required = false
      and d.retry_attempts < d.max_retry_attempts
      and (d.next_retry_at is null or d.next_retry_at <= now())
    order by coalesce(d.next_retry_at, d.last_error_at, now()), d.ctid
    for update skip locked
    limit greatest(1, least(coalesce(p_limit, 10), 100))
  ), claimed as (
    update public.documents d
       set processing_status = 'processing',
           retry_attempts = d.retry_attempts + 1,
           last_error_at = null,
           next_retry_at = null
      from candidates c
     where d.ctid = c.ctid
    returning d.storage_path, d.retry_attempts
  )
  select claimed.storage_path, claimed.retry_attempts from claimed;
end;
$$;


--

-- Name: set_document_processing_status(text, text, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_document_processing_status(p_message_id text, p_storage_path text, p_status text, p_error text DEFAULT NULL::text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
begin
  if p_status not in ('stored','processing','completed','failed') then
    raise exception 'invalid document status: %', p_status;
  end if;

  update public.documents
     set processing_status = p_status,
         processing_error = nullif(p_error, '')
   where storage_path = p_storage_path;

  if not found then
    raise exception 'document not found for storage_path %', p_storage_path;
  end if;
end;
$$;


--

-- Name: worker_heartbeat(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.worker_heartbeat(p_worker_name text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
begin
 insert into public.worker_heartbeats(worker_name,last_seen_at,status,updated_at) values(p_worker_name,now(),'active',now()) on conflict(worker_name) do update set last_seen_at=excluded.last_seen_at,status='active',updated_at=now();
end; $$;


--

-- Name: ai_analyses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_analyses (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    matter_id uuid,
    document_id uuid,
    email_id uuid,
    analysis_type text NOT NULL,
    result jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    status text DEFAULT 'completed'::text NOT NULL,
    model text,
    citations jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_by text DEFAULT 'jafar'::text NOT NULL,
    source_chunks jsonb DEFAULT '[]'::jsonb NOT NULL,
    confidence numeric(5,4),
    requires_lawyer_review boolean DEFAULT true NOT NULL,
    approved_at timestamp with time zone,
    approved_by uuid,
    review_status text DEFAULT 'pending'::text NOT NULL,
    CONSTRAINT ai_analyses_review_status_check CHECK ((review_status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text])))
);


--

-- Name: audit_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    matter_id uuid,
    event_type text NOT NULL,
    actor text NOT NULL,
    object_id text,
    details jsonb DEFAULT '{}'::jsonb NOT NULL,
    occurred_at timestamp with time zone DEFAULT now() NOT NULL
);


--

-- Name: case_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.case_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    event_date date NOT NULL,
    event_type text NOT NULL,
    title text NOT NULL,
    description text,
    source_reference text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--

-- Name: case_graph_evidence; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.case_graph_evidence (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid,
    document_id uuid,
    evidence_type text NOT NULL,
    title text,
    source text,
    source_url text,
    content_hash text,
    extracted_facts jsonb DEFAULT '[]'::jsonb NOT NULL,
    confidence numeric(5,4),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT case_graph_evidence_confidence_check CHECK (((confidence >= (0)::numeric) AND (confidence <= (1)::numeric)))
);


--

-- Name: case_graph_people; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.case_graph_people (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid,
    legal_entity_id uuid,
    person_name text NOT NULL,
    person_identifier text,
    relation_type text NOT NULL,
    role text,
    confidence numeric(5,4),
    evidence_ids jsonb DEFAULT '[]'::jsonb NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT case_graph_people_confidence_check CHECK (((confidence >= (0)::numeric) AND (confidence <= (1)::numeric)))
);


--

-- Name: case_graph_timeline; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.case_graph_timeline (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid,
    event_at timestamp with time zone,
    event_type text NOT NULL,
    title text NOT NULL,
    description text,
    actor_refs jsonb DEFAULT '[]'::jsonb NOT NULL,
    evidence_refs jsonb DEFAULT '[]'::jsonb NOT NULL,
    confidence numeric(5,4),
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT case_graph_timeline_confidence_check CHECK (((confidence >= (0)::numeric) AND (confidence <= (1)::numeric)))
);


--

-- Name: case_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.case_tasks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    task text NOT NULL,
    due_date date,
    status text DEFAULT 'open'::text NOT NULL,
    priority text DEFAULT 'high'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--

-- Name: cases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cases (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_key text NOT NULL,
    case_number text NOT NULL,
    client_name text NOT NULL,
    category text NOT NULL,
    stage text NOT NULL,
    current_investigator text,
    current_body text,
    origin_body text,
    status text DEFAULT 'active'::text NOT NULL,
    next_action text,
    key_date date,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--

-- Name: clients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clients (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    email text,
    phone text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--

-- Name: deadlines; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.deadlines (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    matter_id uuid,
    title text NOT NULL,
    due_at timestamp with time zone,
    status text DEFAULT 'open'::text NOT NULL,
    source_document_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    confidence numeric(5,4),
    requires_approval boolean DEFAULT true NOT NULL,
    basis text
);


--

-- Name: document_chunks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_chunks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_id uuid NOT NULL,
    chunk_index integer NOT NULL,
    content text NOT NULL,
    source_page integer,
    embedding extensions.vector(1536),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--

-- Name: document_ocr_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.document_ocr_jobs ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.document_ocr_jobs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--

-- Name: document_pages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_pages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_id uuid NOT NULL,
    page_number integer NOT NULL,
    image_storage_path text,
    extracted_text text,
    ocr_used boolean DEFAULT false NOT NULL,
    ocr_confidence numeric(5,4),
    status text DEFAULT 'pending'::text NOT NULL,
    error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT document_pages_ocr_confidence_check CHECK (((ocr_confidence >= (0)::numeric) AND (ocr_confidence <= (1)::numeric))),
    CONSTRAINT document_pages_page_number_check CHECK ((page_number > 0)),
    CONSTRAINT document_pages_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'processing'::text, 'completed'::text, 'failed'::text, 'manual_review'::text])))
);


--

-- Name: document_pipeline_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.document_pipeline_jobs ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.document_pipeline_jobs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--

-- Name: document_recovery_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_recovery_jobs (
    id bigint NOT NULL,
    storage_path text NOT NULL,
    status text DEFAULT 'queued'::text NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    available_at timestamp with time zone DEFAULT now() NOT NULL,
    locked_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    lease_expires_at timestamp with time zone,
    CONSTRAINT document_recovery_jobs_attempts_check CHECK ((attempts >= 0)),
    CONSTRAINT document_recovery_jobs_status_check CHECK ((status = ANY (ARRAY['queued'::text, 'processing'::text, 'completed'::text, 'failed'::text])))
);


--

-- Name: document_recovery_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.document_recovery_jobs ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.document_recovery_jobs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--

-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    matter_id uuid,
    filename text NOT NULL,
    content_type text,
    source text NOT NULL,
    storage_path text,
    ocr_required boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    processing_status text DEFAULT 'stored'::text NOT NULL,
    retry_attempts integer DEFAULT 0 NOT NULL,
    last_error_at timestamp with time zone,
    next_retry_at timestamp with time zone,
    max_retry_attempts integer DEFAULT 5 NOT NULL,
    manual_review_required boolean DEFAULT false NOT NULL,
    CONSTRAINT documents_max_retry_attempts_positive CHECK ((max_retry_attempts > 0)),
    CONSTRAINT documents_processing_status_check CHECK ((processing_status = ANY (ARRAY['stored'::text, 'processing'::text, 'completed'::text, 'failed'::text]))),
    CONSTRAINT documents_retry_attempts_nonnegative CHECK ((retry_attempts >= 0))
);


--

-- Name: emails; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.emails (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    message_id text NOT NULL,
    matter_id uuid,
    sender text NOT NULL,
    subject text NOT NULL,
    received_at timestamp with time zone NOT NULL,
    legal_relevant boolean,
    triage_confidence numeric,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    processing_status text DEFAULT 'processed'::text NOT NULL,
    CONSTRAINT emails_processing_status_check CHECK ((processing_status = ANY (ARRAY['claimed'::text, 'processed'::text, 'failed'::text])))
);


--

-- Name: entity_investigation_sources; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.entity_investigation_sources (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    investigation_id uuid NOT NULL,
    source_type text NOT NULL,
    source_name text NOT NULL,
    source_url text,
    query text,
    status text DEFAULT 'pending'::text NOT NULL,
    result jsonb DEFAULT '{}'::jsonb NOT NULL,
    fetched_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--

-- Name: entity_investigations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.entity_investigations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    query text NOT NULL,
    entity_type text,
    inn text,
    ogrn text,
    name text,
    status text DEFAULT 'pending'::text NOT NULL,
    summary jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--

-- Name: jafar_audit_trail; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.jafar_audit_trail (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    action_id text,
    actor text DEFAULT 'jafar'::text NOT NULL,
    event_type text NOT NULL,
    case_id uuid,
    document_id uuid,
    input_refs jsonb DEFAULT '[]'::jsonb NOT NULL,
    reasoning_summary text,
    decision text,
    approval jsonb DEFAULT '{}'::jsonb NOT NULL,
    outcome jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--

-- Name: legal_audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legal_audit_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    actor_id uuid,
    actor_label text,
    action text NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid,
    old_payload jsonb,
    new_payload jsonb,
    device_id text,
    source text DEFAULT 'jafar'::text NOT NULL,
    confirmed boolean DEFAULT false NOT NULL,
    occurred_at timestamp with time zone DEFAULT now() NOT NULL
);


--

-- Name: legal_case_entities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legal_case_entities (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid,
    legal_entity_id uuid,
    relation_type text NOT NULL,
    role text,
    confidence numeric(5,4),
    evidence_ids jsonb DEFAULT '[]'::jsonb NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT legal_case_entities_confidence_check CHECK (((confidence >= (0)::numeric) AND (confidence <= (1)::numeric)))
);


--

-- Name: legal_entities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legal_entities (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    inn text,
    kpp text,
    ogrn text,
    name text NOT NULL,
    normalized_name text,
    entity_type text,
    status text,
    registration_date date,
    address text,
    source_count integer DEFAULT 0 NOT NULL,
    last_verified_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    primary_case_id uuid,
    primary_matter_id uuid
);


--

-- Name: legal_entity_case_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legal_entity_case_links (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    legal_entity_id uuid NOT NULL,
    case_id uuid,
    matter_id uuid,
    relation_type text DEFAULT 'party'::text NOT NULL,
    confidence numeric(5,2) DEFAULT 100 NOT NULL,
    evidence jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT legal_entity_case_links_check CHECK (((case_id IS NOT NULL) OR (matter_id IS NOT NULL)))
);


--

-- Name: legal_entity_research_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legal_entity_research_audit (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    research_run_id uuid,
    legal_entity_id uuid,
    case_id uuid,
    matter_id uuid,
    action text NOT NULL,
    actor text DEFAULT 'jafar'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL
);


--

-- Name: legal_entity_research_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legal_entity_research_runs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    legal_entity_id uuid,
    query text NOT NULL,
    query_type text NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    status text DEFAULT 'running'::text NOT NULL,
    sources_requested text[] DEFAULT '{}'::text[] NOT NULL,
    sources_completed text[] DEFAULT '{}'::text[] NOT NULL,
    findings jsonb DEFAULT '{}'::jsonb NOT NULL
);


--

-- Name: legal_entity_research_sources; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legal_entity_research_sources (
    source_key text NOT NULL,
    display_name text NOT NULL,
    category text NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    requires_auth boolean DEFAULT false NOT NULL,
    notes text
);


--

-- Name: legal_entity_source_checks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legal_entity_source_checks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    legal_entity_id uuid,
    source text NOT NULL,
    query_name text,
    query_inn text,
    query_ogrn text,
    query_kpp text,
    status text NOT NULL,
    checked_at timestamp with time zone DEFAULT now() NOT NULL,
    source_url text,
    data jsonb DEFAULT '{}'::jsonb NOT NULL,
    error text,
    confidence numeric(5,4),
    CONSTRAINT legal_entity_source_checks_confidence_check CHECK (((confidence >= (0)::numeric) AND (confidence <= (1)::numeric))),
    CONSTRAINT legal_entity_source_checks_status_check CHECK ((status = ANY (ARRAY['found'::text, 'negative'::text, 'no_data'::text, 'error'::text, 'timeout'::text])))
);


--

-- Name: legal_entity_source_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legal_entity_source_results (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    legal_entity_id uuid NOT NULL,
    source_key text NOT NULL,
    source_url text,
    checked_at timestamp with time zone DEFAULT now() NOT NULL,
    status text,
    data jsonb DEFAULT '{}'::jsonb NOT NULL,
    error text
);


--

-- Name: matter_aliases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.matter_aliases (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    matter_id uuid NOT NULL,
    alias text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--

-- Name: matters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.matters (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    client_id uuid,
    title text NOT NULL,
    matter_type text NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    case_number text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    owner_user_id text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL
);


--

-- Name: recovery_worker_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recovery_worker_runs (
    id bigint NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    claimed_count integer DEFAULT 0 NOT NULL,
    status text DEFAULT 'running'::text NOT NULL,
    error text,
    CONSTRAINT recovery_worker_runs_status_check CHECK ((status = ANY (ARRAY['running'::text, 'completed'::text, 'failed'::text])))
);


--

-- Name: recovery_worker_health; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.recovery_worker_health WITH (security_invoker='true') AS
 SELECT count(*) FILTER (WHERE (status = 'completed'::text)) AS completed_runs,
    count(*) FILTER (WHERE (status = 'failed'::text)) AS failed_runs,
    count(*) FILTER (WHERE (status = 'running'::text)) AS running_runs,
    COALESCE(sum(claimed_count) FILTER (WHERE (status = 'completed'::text)), (0)::bigint) AS documents_claimed,
    max(finished_at) FILTER (WHERE (status = 'completed'::text)) AS last_completed_at,
    max(finished_at) FILTER (WHERE (status = 'failed'::text)) AS last_failed_at
   FROM public.recovery_worker_runs;


--

-- Name: recovery_worker_incidents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recovery_worker_incidents (
    id bigint NOT NULL,
    detected_at timestamp with time zone DEFAULT now() NOT NULL,
    incident_type text NOT NULL,
    severity text DEFAULT 'warning'::text NOT NULL,
    details text,
    resolved_at timestamp with time zone,
    CONSTRAINT recovery_incident_severity_check CHECK ((severity = ANY (ARRAY['warning'::text, 'critical'::text]))),
    CONSTRAINT recovery_incident_type_check CHECK ((incident_type = ANY (ARRAY['worker_stale'::text, 'worker_failed'::text, 'worker_running_too_long'::text])))
);


--

-- Name: recovery_worker_incidents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.recovery_worker_incidents ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.recovery_worker_incidents_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--

-- Name: recovery_worker_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.recovery_worker_runs ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.recovery_worker_runs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--

-- Name: sync_conflicts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sync_conflicts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    local_version bigint NOT NULL,
    remote_version bigint NOT NULL,
    local_payload jsonb NOT NULL,
    remote_payload jsonb NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    resolved_at timestamp with time zone,
    resolved_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sync_conflicts_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'resolved_local'::text, 'resolved_remote'::text, 'cancelled'::text])))
);


--

-- Name: sync_metadata; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sync_metadata (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id text NOT NULL,
    device_id text NOT NULL,
    entity_type text NOT NULL,
    entity_id text NOT NULL,
    version bigint DEFAULT 1 NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--

-- Name: telegram_approval_queue; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.telegram_approval_queue (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    channel_id text,
    chat_id text,
    direction text NOT NULL,
    content text NOT NULL,
    proposed_action text NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    case_id uuid,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    reviewed_at timestamp with time zone,
    CONSTRAINT telegram_approval_queue_direction_check CHECK ((direction = ANY (ARRAY['incoming'::text, 'outgoing'::text]))),
    CONSTRAINT telegram_approval_queue_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text, 'published'::text])))
);


--

-- Name: telegram_comment_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.telegram_comment_audit (
    id bigint NOT NULL,
    update_id bigint NOT NULL,
    chat_id text NOT NULL,
    message_id bigint NOT NULL,
    user_id text,
    username text,
    intent text NOT NULL,
    decision_mode text NOT NULL,
    draft text NOT NULL,
    status text DEFAULT 'draft'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--

-- Name: telegram_comment_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.telegram_comment_audit ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.telegram_comment_audit_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--

-- Name: telegram_comment_queue_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.telegram_comment_queue ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.telegram_comment_queue_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--

-- Name: telegram_editorial_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.telegram_editorial_events (
    id bigint NOT NULL,
    event_type text NOT NULL,
    external_id text,
    status text DEFAULT 'new'::text NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    processed_at timestamp with time zone
);


--

-- Name: telegram_editorial_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.telegram_editorial_events ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.telegram_editorial_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--

-- Name: telegram_inbound_updates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.telegram_inbound_updates (
    update_id bigint NOT NULL,
    status text DEFAULT 'claimed'::text NOT NULL,
    claimed_at timestamp with time zone DEFAULT now() NOT NULL,
    processed_at timestamp with time zone,
    error text,
    CONSTRAINT telegram_inbound_updates_status_check CHECK ((status = ANY (ARRAY['claimed'::text, 'processed'::text, 'failed'::text])))
);


--

-- Name: telegram_metrics_daily; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.telegram_metrics_daily (
    id bigint NOT NULL,
    report_date date NOT NULL,
    views bigint DEFAULT 0 NOT NULL,
    reactions bigint DEFAULT 0 NOT NULL,
    comments bigint DEFAULT 0 NOT NULL,
    forwards bigint DEFAULT 0 NOT NULL,
    new_subscribers bigint DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--

-- Name: telegram_metrics_daily_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.telegram_metrics_daily ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.telegram_metrics_daily_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--

-- Name: telegram_publications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.telegram_publications ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.telegram_publications_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--

-- Name: telegram_worker_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.telegram_worker_runs (
    id bigint NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    recovered integer DEFAULT 0 NOT NULL,
    claimed integer DEFAULT 0 NOT NULL,
    published integer DEFAULT 0 NOT NULL,
    failed integer DEFAULT 0 NOT NULL,
    status text DEFAULT 'running'::text NOT NULL,
    error text
);


--

-- Name: telegram_worker_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.telegram_worker_runs ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.telegram_worker_runs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--

-- Name: worker_heartbeats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.worker_heartbeats (
    worker_name text NOT NULL,
    last_seen_at timestamp with time zone DEFAULT now() NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--

-- Name: ai_analyses ai_analyses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_analyses
    ADD CONSTRAINT ai_analyses_pkey PRIMARY KEY (id);


--

-- Name: audit_events audit_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_pkey PRIMARY KEY (id);


--

-- Name: case_events case_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.case_events
    ADD CONSTRAINT case_events_pkey PRIMARY KEY (id);


--

-- Name: case_graph_evidence case_graph_evidence_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.case_graph_evidence
    ADD CONSTRAINT case_graph_evidence_pkey PRIMARY KEY (id);


--

-- Name: case_graph_people case_graph_people_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.case_graph_people
    ADD CONSTRAINT case_graph_people_pkey PRIMARY KEY (id);


--

-- Name: case_graph_timeline case_graph_timeline_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.case_graph_timeline
    ADD CONSTRAINT case_graph_timeline_pkey PRIMARY KEY (id);


--

-- Name: case_tasks case_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.case_tasks
    ADD CONSTRAINT case_tasks_pkey PRIMARY KEY (id);


--

-- Name: cases cases_case_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cases
    ADD CONSTRAINT cases_case_key_key UNIQUE (case_key);


--

-- Name: cases cases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cases
    ADD CONSTRAINT cases_pkey PRIMARY KEY (id);


--

-- Name: clients clients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clients
    ADD CONSTRAINT clients_pkey PRIMARY KEY (id);


--

-- Name: deadlines deadlines_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deadlines
    ADD CONSTRAINT deadlines_pkey PRIMARY KEY (id);


--

-- Name: document_chunks document_chunks_document_id_chunk_index_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_chunks
    ADD CONSTRAINT document_chunks_document_id_chunk_index_key UNIQUE (document_id, chunk_index);


--

-- Name: document_chunks document_chunks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_chunks
    ADD CONSTRAINT document_chunks_pkey PRIMARY KEY (id);


--

-- Name: document_ocr_jobs document_ocr_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_ocr_jobs
    ADD CONSTRAINT document_ocr_jobs_pkey PRIMARY KEY (id);


--

-- Name: document_pages document_pages_document_id_page_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_pages
    ADD CONSTRAINT document_pages_document_id_page_number_key UNIQUE (document_id, page_number);


--

-- Name: document_pages document_pages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_pages
    ADD CONSTRAINT document_pages_pkey PRIMARY KEY (id);


--

-- Name: document_pipeline_jobs document_pipeline_jobs_document_id_stage_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_pipeline_jobs
    ADD CONSTRAINT document_pipeline_jobs_document_id_stage_key UNIQUE (document_id, stage);


--

-- Name: document_pipeline_jobs document_pipeline_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_pipeline_jobs
    ADD CONSTRAINT document_pipeline_jobs_pkey PRIMARY KEY (id);


--

-- Name: document_recovery_jobs document_recovery_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_recovery_jobs
    ADD CONSTRAINT document_recovery_jobs_pkey PRIMARY KEY (id);


--

-- Name: document_recovery_jobs document_recovery_jobs_storage_path_status_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_recovery_jobs
    ADD CONSTRAINT document_recovery_jobs_storage_path_status_key UNIQUE (storage_path, status);


--

-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--

-- Name: emails emails_message_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emails
    ADD CONSTRAINT emails_message_id_key UNIQUE (message_id);


--

-- Name: emails emails_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emails
    ADD CONSTRAINT emails_pkey PRIMARY KEY (id);


--

-- Name: entity_investigation_sources entity_investigation_sources_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_investigation_sources
    ADD CONSTRAINT entity_investigation_sources_pkey PRIMARY KEY (id);


--

-- Name: entity_investigations entity_investigations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_investigations
    ADD CONSTRAINT entity_investigations_pkey PRIMARY KEY (id);


--

-- Name: jafar_audit_trail jafar_audit_trail_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jafar_audit_trail
    ADD CONSTRAINT jafar_audit_trail_pkey PRIMARY KEY (id);


--

-- Name: legal_audit_log legal_audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_audit_log
    ADD CONSTRAINT legal_audit_log_pkey PRIMARY KEY (id);


--

-- Name: legal_case_entities legal_case_entities_case_id_legal_entity_id_relation_type_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_case_entities
    ADD CONSTRAINT legal_case_entities_case_id_legal_entity_id_relation_type_key UNIQUE (case_id, legal_entity_id, relation_type);


--

-- Name: legal_case_entities legal_case_entities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_case_entities
    ADD CONSTRAINT legal_case_entities_pkey PRIMARY KEY (id);


--

-- Name: legal_entities legal_entities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entities
    ADD CONSTRAINT legal_entities_pkey PRIMARY KEY (id);


--

-- Name: legal_entity_case_links legal_entity_case_links_legal_entity_id_case_id_matter_id_r_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entity_case_links
    ADD CONSTRAINT legal_entity_case_links_legal_entity_id_case_id_matter_id_r_key UNIQUE (legal_entity_id, case_id, matter_id, relation_type);


--

-- Name: legal_entity_case_links legal_entity_case_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entity_case_links
    ADD CONSTRAINT legal_entity_case_links_pkey PRIMARY KEY (id);


--

-- Name: legal_entity_research_audit legal_entity_research_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entity_research_audit
    ADD CONSTRAINT legal_entity_research_audit_pkey PRIMARY KEY (id);


--

-- Name: legal_entity_research_runs legal_entity_research_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entity_research_runs
    ADD CONSTRAINT legal_entity_research_runs_pkey PRIMARY KEY (id);


--

-- Name: legal_entity_research_sources legal_entity_research_sources_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entity_research_sources
    ADD CONSTRAINT legal_entity_research_sources_pkey PRIMARY KEY (source_key);


--

-- Name: legal_entity_source_checks legal_entity_source_checks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entity_source_checks
    ADD CONSTRAINT legal_entity_source_checks_pkey PRIMARY KEY (id);


--

-- Name: legal_entity_source_results legal_entity_source_results_legal_entity_id_source_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entity_source_results
    ADD CONSTRAINT legal_entity_source_results_legal_entity_id_source_key_key UNIQUE (legal_entity_id, source_key);


--

-- Name: legal_entity_source_results legal_entity_source_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entity_source_results
    ADD CONSTRAINT legal_entity_source_results_pkey PRIMARY KEY (id);


--

-- Name: matter_aliases matter_aliases_matter_id_alias_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matter_aliases
    ADD CONSTRAINT matter_aliases_matter_id_alias_key UNIQUE (matter_id, alias);


--

-- Name: matter_aliases matter_aliases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matter_aliases
    ADD CONSTRAINT matter_aliases_pkey PRIMARY KEY (id);


--

-- Name: matter_events matter_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matter_events
    ADD CONSTRAINT matter_events_pkey PRIMARY KEY (id);


--

-- Name: matters matters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matters
    ADD CONSTRAINT matters_pkey PRIMARY KEY (id);


--

-- Name: recovery_worker_incidents recovery_worker_incidents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recovery_worker_incidents
    ADD CONSTRAINT recovery_worker_incidents_pkey PRIMARY KEY (id);


--

-- Name: recovery_worker_runs recovery_worker_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recovery_worker_runs
    ADD CONSTRAINT recovery_worker_runs_pkey PRIMARY KEY (id);


--

-- Name: sync_conflicts sync_conflicts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_conflicts
    ADD CONSTRAINT sync_conflicts_pkey PRIMARY KEY (id);


--

-- Name: sync_metadata sync_metadata_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_metadata
    ADD CONSTRAINT sync_metadata_pkey PRIMARY KEY (id);


--

-- Name: sync_metadata sync_metadata_user_id_device_id_entity_type_entity_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_metadata
    ADD CONSTRAINT sync_metadata_user_id_device_id_entity_type_entity_id_key UNIQUE (user_id, device_id, entity_type, entity_id);


--

-- Name: telegram_approval_queue telegram_approval_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_approval_queue
    ADD CONSTRAINT telegram_approval_queue_pkey PRIMARY KEY (id);


--

-- Name: telegram_comment_audit telegram_comment_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_comment_audit
    ADD CONSTRAINT telegram_comment_audit_pkey PRIMARY KEY (id);


--

-- Name: telegram_comment_queue telegram_comment_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_comment_queue
    ADD CONSTRAINT telegram_comment_queue_pkey PRIMARY KEY (id);


--

-- Name: telegram_editorial_events telegram_editorial_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_editorial_events
    ADD CONSTRAINT telegram_editorial_events_pkey PRIMARY KEY (id);


--

-- Name: telegram_inbound_updates telegram_inbound_updates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_inbound_updates
    ADD CONSTRAINT telegram_inbound_updates_pkey PRIMARY KEY (update_id);


--

-- Name: telegram_metrics_daily telegram_metrics_daily_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_metrics_daily
    ADD CONSTRAINT telegram_metrics_daily_pkey PRIMARY KEY (id);


--

-- Name: telegram_metrics_daily telegram_metrics_daily_report_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_metrics_daily
    ADD CONSTRAINT telegram_metrics_daily_report_date_key UNIQUE (report_date);


--

-- Name: telegram_publications telegram_publications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_publications
    ADD CONSTRAINT telegram_publications_pkey PRIMARY KEY (id);


--

-- Name: telegram_worker_runs telegram_worker_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_worker_runs
    ADD CONSTRAINT telegram_worker_runs_pkey PRIMARY KEY (id);


--

-- Name: worker_heartbeats worker_heartbeats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.worker_heartbeats
    ADD CONSTRAINT worker_heartbeats_pkey PRIMARY KEY (worker_name);


--

-- Name: case_events_case_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX case_events_case_id_idx ON public.case_events USING btree (case_id);


--

-- Name: case_graph_evidence_case_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX case_graph_evidence_case_idx ON public.case_graph_evidence USING btree (case_id, created_at DESC);


--

-- Name: case_graph_evidence_document_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX case_graph_evidence_document_id_idx ON public.case_graph_evidence USING btree (document_id);


--

-- Name: case_graph_people_case_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX case_graph_people_case_idx ON public.case_graph_people USING btree (case_id);


--

-- Name: case_graph_people_entity_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX case_graph_people_entity_idx ON public.case_graph_people USING btree (legal_entity_id);


--

-- Name: case_graph_people_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX case_graph_people_name_idx ON public.case_graph_people USING btree (person_name);


--

-- Name: case_graph_timeline_case_date_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX case_graph_timeline_case_date_idx ON public.case_graph_timeline USING btree (case_id, event_at);


--

-- Name: case_tasks_case_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX case_tasks_case_id_idx ON public.case_tasks USING btree (case_id);


--

-- Name: deadlines_source_document_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX deadlines_source_document_id_idx ON public.deadlines USING btree (source_document_id);


--

-- Name: document_ocr_jobs_owner_claim_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX document_ocr_jobs_owner_claim_idx ON public.document_ocr_jobs USING btree (document_id, status, available_at, created_at);


--

-- Name: document_ocr_jobs_ready_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX document_ocr_jobs_ready_idx ON public.document_ocr_jobs USING btree (status, available_at, created_at) WHERE (status = 'queued'::text);


--

-- Name: document_pages_ready_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX document_pages_ready_idx ON public.document_pages USING btree (document_id, status, page_number) WHERE (status = ANY (ARRAY['pending'::text, 'processing'::text, 'manual_review'::text]));


--

-- Name: document_recovery_jobs_active_path_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX document_recovery_jobs_active_path_idx ON public.document_recovery_jobs USING btree (storage_path) WHERE (status = ANY (ARRAY['queued'::text, 'processing'::text]));


--

-- Name: document_recovery_jobs_due_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX document_recovery_jobs_due_idx ON public.document_recovery_jobs USING btree (status, available_at);


--

-- Name: document_recovery_jobs_lease_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX document_recovery_jobs_lease_idx ON public.document_recovery_jobs USING btree (status, lease_expires_at);


--

-- Name: document_recovery_jobs_ready_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX document_recovery_jobs_ready_idx ON public.document_recovery_jobs USING btree (available_at) WHERE (status = 'queued'::text);


--

-- Name: entity_investigations_inn_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX entity_investigations_inn_idx ON public.entity_investigations USING btree (inn);


--

-- Name: entity_investigations_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX entity_investigations_name_idx ON public.entity_investigations USING btree (name);


--

-- Name: entity_investigations_ogrn_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX entity_investigations_ogrn_idx ON public.entity_investigations USING btree (ogrn);


--

-- Name: entity_sources_investigation_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX entity_sources_investigation_idx ON public.entity_investigation_sources USING btree (investigation_id);


--

-- Name: idx_ai_analyses_document_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_analyses_document_created_at ON public.ai_analyses USING btree (document_id, created_at DESC);


--

-- Name: idx_ai_analyses_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_analyses_document_id ON public.ai_analyses USING btree (document_id);


--

-- Name: idx_ai_analyses_document_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_analyses_document_status ON public.ai_analyses USING btree (document_id, status, created_at DESC);


--

-- Name: idx_ai_analyses_email_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_analyses_email_id ON public.ai_analyses USING btree (email_id);


--

-- Name: idx_ai_analyses_matter_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_analyses_matter_created_at ON public.ai_analyses USING btree (matter_id, created_at DESC);


--

-- Name: idx_ai_analyses_matter_document; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_analyses_matter_document ON public.ai_analyses USING btree (matter_id, document_id);


--

-- Name: idx_analyses_matter_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_analyses_matter_id ON public.ai_analyses USING btree (matter_id);


--

-- Name: idx_audit_matter_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_matter_id ON public.audit_events USING btree (matter_id);


--

-- Name: idx_deadlines_matter_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deadlines_matter_id ON public.deadlines USING btree (matter_id);


--

-- Name: idx_document_chunks_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_document_chunks_document_id ON public.document_chunks USING btree (document_id);


--

-- Name: idx_document_chunks_document_id_chunk_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_document_chunks_document_id_chunk_index ON public.document_chunks USING btree (document_id, chunk_index);


--

-- Name: idx_document_chunks_embedding; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_document_chunks_embedding ON public.document_chunks USING hnsw (embedding extensions.vector_cosine_ops);


--

-- Name: idx_document_ocr_jobs_claim; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_document_ocr_jobs_claim ON public.document_ocr_jobs USING btree (status, available_at);


--

-- Name: idx_document_ocr_jobs_document; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_document_ocr_jobs_document ON public.document_ocr_jobs USING btree (document_id);


--

-- Name: idx_document_pages_document_page; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_document_pages_document_page ON public.document_pages USING btree (document_id, page_number);


--

-- Name: idx_document_pages_document_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_document_pages_document_status ON public.document_pages USING btree (document_id, status, page_number);


--

-- Name: idx_documents_matter_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_matter_id ON public.documents USING btree (matter_id);


--

-- Name: idx_documents_matter_id_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_matter_id_id ON public.documents USING btree (matter_id, id);


--

-- Name: idx_emails_matter_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_emails_matter_id ON public.emails USING btree (matter_id);


--

-- Name: idx_emails_matter_id_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_emails_matter_id_id ON public.emails USING btree (matter_id, id);


--

-- Name: idx_emails_processing_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_emails_processing_status ON public.emails USING btree (processing_status);


--

-- Name: idx_legal_entity_research_audit_matter_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_legal_entity_research_audit_matter_id ON public.legal_entity_research_audit USING btree (matter_id);


--

-- Name: idx_matter_aliases_alias; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_matter_aliases_alias ON public.matter_aliases USING btree (alias);


--

-- Name: idx_matter_aliases_matter_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_matter_aliases_matter_id ON public.matter_aliases USING btree (matter_id);


--

-- Name: idx_matter_events_owner_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_matter_events_owner_user_id ON public.matter_events USING btree (owner_user_id);


--

-- Name: idx_matters_client_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_matters_client_id ON public.matters USING btree (client_id);


--

-- Name: idx_matters_owner_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_matters_owner_user_id ON public.matters USING btree (owner_user_id);


--

-- Name: idx_ocr_jobs_recovery; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ocr_jobs_recovery ON public.document_ocr_jobs USING btree (status, lease_expires_at) WHERE (status = 'processing'::text);


--

-- Name: idx_pipeline_claim; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pipeline_claim ON public.document_pipeline_jobs USING btree (stage, status, available_at, created_at) WHERE (status = 'queued'::text);


--

-- Name: idx_pipeline_jobs_recovery; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pipeline_jobs_recovery ON public.document_pipeline_jobs USING btree (status, lease_expires_at) WHERE (status = 'processing'::text);


--

-- Name: idx_sync_metadata_user_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sync_metadata_user_entity ON public.sync_metadata USING btree (user_id, entity_type, entity_id);


--

-- Name: idx_telegram_comment_audit_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_telegram_comment_audit_user_id ON public.telegram_comment_audit USING btree (user_id);


--

-- Name: jafar_audit_action_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX jafar_audit_action_idx ON public.jafar_audit_trail USING btree (action_id);


--

-- Name: jafar_audit_case_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX jafar_audit_case_idx ON public.jafar_audit_trail USING btree (case_id, created_at DESC);


--

-- Name: jafar_audit_created_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX jafar_audit_created_idx ON public.jafar_audit_trail USING btree (created_at DESC);


--

-- Name: jafar_audit_trail_document_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX jafar_audit_trail_document_id_idx ON public.jafar_audit_trail USING btree (document_id);


--

-- Name: legal_audit_log_actor_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX legal_audit_log_actor_idx ON public.legal_audit_log USING btree (actor_id, occurred_at DESC);


--

-- Name: legal_audit_log_entity_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX legal_audit_log_entity_idx ON public.legal_audit_log USING btree (entity_type, entity_id, occurred_at DESC);


--

-- Name: legal_case_entities_case_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX legal_case_entities_case_idx ON public.legal_case_entities USING btree (case_id);


--

-- Name: legal_case_entities_entity_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX legal_case_entities_entity_idx ON public.legal_case_entities USING btree (legal_entity_id);


--

-- Name: legal_entities_case_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX legal_entities_case_idx ON public.legal_entities USING btree (primary_case_id);


--

-- Name: legal_entities_inn_uidx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX legal_entities_inn_uidx ON public.legal_entities USING btree (inn) WHERE (inn IS NOT NULL);


--

-- Name: legal_entities_matter_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX legal_entities_matter_idx ON public.legal_entities USING btree (primary_matter_id);


--

-- Name: legal_entities_name_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX legal_entities_name_idx ON public.legal_entities USING btree (normalized_name);


--

-- Name: legal_entities_ogrn_uidx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX legal_entities_ogrn_uidx ON public.legal_entities USING btree (ogrn) WHERE (ogrn IS NOT NULL);


--

-- Name: legal_entity_case_links_case_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX legal_entity_case_links_case_idx ON public.legal_entity_case_links USING btree (case_id);


--

-- Name: legal_entity_case_links_entity_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX legal_entity_case_links_entity_idx ON public.legal_entity_case_links USING btree (legal_entity_id);


--

-- Name: legal_entity_case_links_matter_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX legal_entity_case_links_matter_idx ON public.legal_entity_case_links USING btree (matter_id);


--

-- Name: legal_entity_research_audit_case_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX legal_entity_research_audit_case_idx ON public.legal_entity_research_audit USING btree (case_id, created_at DESC);


--

-- Name: legal_entity_research_audit_entity_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX legal_entity_research_audit_entity_idx ON public.legal_entity_research_audit USING btree (legal_entity_id, created_at DESC);


--

-- Name: legal_entity_source_checks_entity_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX legal_entity_source_checks_entity_idx ON public.legal_entity_source_checks USING btree (legal_entity_id, checked_at DESC);


--

-- Name: legal_entity_source_checks_source_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX legal_entity_source_checks_source_idx ON public.legal_entity_source_checks USING btree (source, status);


--

-- Name: matter_events_matter_document_fingerprint_uidx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX matter_events_matter_document_fingerprint_uidx ON public.matter_events USING btree (matter_id, document_fingerprint) WHERE (document_fingerprint IS NOT NULL);


--

-- Name: matter_events_matter_id_event_date_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX matter_events_matter_id_event_date_idx ON public.matter_events USING btree (matter_id, event_date DESC);


--

-- Name: sync_conflicts_pending_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX sync_conflicts_pending_idx ON public.sync_conflicts USING btree (status, created_at DESC);


--

-- Name: telegram_approval_queue_case_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX telegram_approval_queue_case_idx ON public.telegram_approval_queue USING btree (case_id);


--

-- Name: telegram_approval_queue_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX telegram_approval_queue_status_idx ON public.telegram_approval_queue USING btree (status, created_at DESC);


--

-- Name: telegram_comment_audit_created_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX telegram_comment_audit_created_idx ON public.telegram_comment_audit USING btree (created_at DESC);


--

-- Name: telegram_comment_audit_update_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX telegram_comment_audit_update_idx ON public.telegram_comment_audit USING btree (update_id);


--

-- Name: telegram_comment_queue_resolved_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX telegram_comment_queue_resolved_idx ON public.telegram_comment_queue USING btree (status, resolved_at DESC);


--

-- Name: telegram_comment_queue_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX telegram_comment_queue_status_idx ON public.telegram_comment_queue USING btree (status, created_at DESC);


--

-- Name: telegram_editorial_events_external_id_uidx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX telegram_editorial_events_external_id_uidx ON public.telegram_editorial_events USING btree (external_id) WHERE (external_id IS NOT NULL);


--

-- Name: telegram_editorial_events_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX telegram_editorial_events_status_idx ON public.telegram_editorial_events USING btree (status, created_at DESC);


--

-- Name: telegram_inbound_updates_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX telegram_inbound_updates_status_idx ON public.telegram_inbound_updates USING btree (status);


--

-- Name: telegram_publications_claim_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX telegram_publications_claim_idx ON public.telegram_publications USING btree (status, scheduled_at, claimed_at);


--

-- Name: telegram_publications_lease_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX telegram_publications_lease_idx ON public.telegram_publications USING btree (status, claimed_at);


--

-- Name: telegram_publications_schedule_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX telegram_publications_schedule_idx ON public.telegram_publications USING btree (status, scheduled_at);


--

-- Name: telegram_worker_runs_started_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX telegram_worker_runs_started_idx ON public.telegram_worker_runs USING btree (started_at DESC);


--

-- Name: uq_document_ocr_jobs_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_document_ocr_jobs_document_id ON public.document_ocr_jobs USING btree (document_id);


--

-- Name: ai_analyses ai_analyses_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_analyses
    ADD CONSTRAINT ai_analyses_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--

-- Name: ai_analyses ai_analyses_email_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_analyses
    ADD CONSTRAINT ai_analyses_email_id_fkey FOREIGN KEY (email_id) REFERENCES public.emails(id) ON DELETE SET NULL;


--

-- Name: ai_analyses ai_analyses_matter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_analyses
    ADD CONSTRAINT ai_analyses_matter_id_fkey FOREIGN KEY (matter_id) REFERENCES public.matters(id) ON DELETE CASCADE;


--

-- Name: audit_events audit_events_matter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_matter_id_fkey FOREIGN KEY (matter_id) REFERENCES public.matters(id) ON DELETE SET NULL;


--

-- Name: case_events case_events_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.case_events
    ADD CONSTRAINT case_events_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE CASCADE;


--

-- Name: case_graph_evidence case_graph_evidence_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.case_graph_evidence
    ADD CONSTRAINT case_graph_evidence_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE CASCADE;


--

-- Name: case_graph_evidence case_graph_evidence_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.case_graph_evidence
    ADD CONSTRAINT case_graph_evidence_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--

-- Name: case_graph_people case_graph_people_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.case_graph_people
    ADD CONSTRAINT case_graph_people_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE CASCADE;


--

-- Name: case_graph_people case_graph_people_legal_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.case_graph_people
    ADD CONSTRAINT case_graph_people_legal_entity_id_fkey FOREIGN KEY (legal_entity_id) REFERENCES public.legal_entities(id) ON DELETE CASCADE;


--

-- Name: case_graph_timeline case_graph_timeline_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.case_graph_timeline
    ADD CONSTRAINT case_graph_timeline_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE CASCADE;


--

-- Name: case_tasks case_tasks_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.case_tasks
    ADD CONSTRAINT case_tasks_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE CASCADE;


--

-- Name: deadlines deadlines_matter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deadlines
    ADD CONSTRAINT deadlines_matter_id_fkey FOREIGN KEY (matter_id) REFERENCES public.matters(id) ON DELETE CASCADE;


--

-- Name: deadlines deadlines_source_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deadlines
    ADD CONSTRAINT deadlines_source_document_id_fkey FOREIGN KEY (source_document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--

-- Name: document_chunks document_chunks_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_chunks
    ADD CONSTRAINT document_chunks_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--

-- Name: document_ocr_jobs document_ocr_jobs_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_ocr_jobs
    ADD CONSTRAINT document_ocr_jobs_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--

-- Name: document_pages document_pages_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_pages
    ADD CONSTRAINT document_pages_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--

-- Name: document_pipeline_jobs document_pipeline_jobs_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_pipeline_jobs
    ADD CONSTRAINT document_pipeline_jobs_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--

-- Name: documents documents_matter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_matter_id_fkey FOREIGN KEY (matter_id) REFERENCES public.matters(id) ON DELETE SET NULL;


--

-- Name: emails emails_matter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.emails
    ADD CONSTRAINT emails_matter_id_fkey FOREIGN KEY (matter_id) REFERENCES public.matters(id) ON DELETE SET NULL;


--

-- Name: entity_investigation_sources entity_investigation_sources_investigation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_investigation_sources
    ADD CONSTRAINT entity_investigation_sources_investigation_id_fkey FOREIGN KEY (investigation_id) REFERENCES public.entity_investigations(id) ON DELETE CASCADE;


--

-- Name: jafar_audit_trail jafar_audit_trail_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jafar_audit_trail
    ADD CONSTRAINT jafar_audit_trail_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE SET NULL;


--

-- Name: jafar_audit_trail jafar_audit_trail_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jafar_audit_trail
    ADD CONSTRAINT jafar_audit_trail_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--

-- Name: legal_case_entities legal_case_entities_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_case_entities
    ADD CONSTRAINT legal_case_entities_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE CASCADE;


--

-- Name: legal_case_entities legal_case_entities_legal_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_case_entities
    ADD CONSTRAINT legal_case_entities_legal_entity_id_fkey FOREIGN KEY (legal_entity_id) REFERENCES public.legal_entities(id) ON DELETE CASCADE;


--

-- Name: legal_entities legal_entities_primary_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entities
    ADD CONSTRAINT legal_entities_primary_case_id_fkey FOREIGN KEY (primary_case_id) REFERENCES public.cases(id) ON DELETE SET NULL;


--

-- Name: legal_entities legal_entities_primary_matter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entities
    ADD CONSTRAINT legal_entities_primary_matter_id_fkey FOREIGN KEY (primary_matter_id) REFERENCES public.matters(id) ON DELETE SET NULL;


--

-- Name: legal_entity_case_links legal_entity_case_links_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entity_case_links
    ADD CONSTRAINT legal_entity_case_links_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE CASCADE;


--

-- Name: legal_entity_case_links legal_entity_case_links_legal_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entity_case_links
    ADD CONSTRAINT legal_entity_case_links_legal_entity_id_fkey FOREIGN KEY (legal_entity_id) REFERENCES public.legal_entities(id) ON DELETE CASCADE;


--

-- Name: legal_entity_case_links legal_entity_case_links_matter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entity_case_links
    ADD CONSTRAINT legal_entity_case_links_matter_id_fkey FOREIGN KEY (matter_id) REFERENCES public.matters(id) ON DELETE CASCADE;


--

-- Name: legal_entity_research_audit legal_entity_research_audit_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entity_research_audit
    ADD CONSTRAINT legal_entity_research_audit_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE SET NULL;


--

-- Name: legal_entity_research_audit legal_entity_research_audit_legal_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entity_research_audit
    ADD CONSTRAINT legal_entity_research_audit_legal_entity_id_fkey FOREIGN KEY (legal_entity_id) REFERENCES public.legal_entities(id) ON DELETE SET NULL;


--

-- Name: legal_entity_research_audit legal_entity_research_audit_matter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entity_research_audit
    ADD CONSTRAINT legal_entity_research_audit_matter_id_fkey FOREIGN KEY (matter_id) REFERENCES public.matters(id) ON DELETE SET NULL;


--

-- Name: legal_entity_research_audit legal_entity_research_audit_research_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entity_research_audit
    ADD CONSTRAINT legal_entity_research_audit_research_run_id_fkey FOREIGN KEY (research_run_id) REFERENCES public.legal_entity_research_runs(id) ON DELETE SET NULL;


--

-- Name: legal_entity_research_runs legal_entity_research_runs_legal_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entity_research_runs
    ADD CONSTRAINT legal_entity_research_runs_legal_entity_id_fkey FOREIGN KEY (legal_entity_id) REFERENCES public.legal_entities(id) ON DELETE SET NULL;


--

-- Name: legal_entity_source_checks legal_entity_source_checks_legal_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entity_source_checks
    ADD CONSTRAINT legal_entity_source_checks_legal_entity_id_fkey FOREIGN KEY (legal_entity_id) REFERENCES public.legal_entities(id) ON DELETE CASCADE;


--

-- Name: legal_entity_source_results legal_entity_source_results_legal_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legal_entity_source_results
    ADD CONSTRAINT legal_entity_source_results_legal_entity_id_fkey FOREIGN KEY (legal_entity_id) REFERENCES public.legal_entities(id) ON DELETE CASCADE;


--

-- Name: matter_aliases matter_aliases_matter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matter_aliases
    ADD CONSTRAINT matter_aliases_matter_id_fkey FOREIGN KEY (matter_id) REFERENCES public.matters(id) ON DELETE CASCADE;


--

-- Name: matter_events matter_events_matter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matter_events
    ADD CONSTRAINT matter_events_matter_id_fkey FOREIGN KEY (matter_id) REFERENCES public.matters(id) ON DELETE CASCADE;


--

-- Name: matters matters_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matters
    ADD CONSTRAINT matters_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id) ON DELETE SET NULL;


--

-- Name: telegram_approval_queue telegram_approval_queue_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_approval_queue
    ADD CONSTRAINT telegram_approval_queue_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE SET NULL;


--

-- Name: telegram_comment_audit telegram_comment_audit_update_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_comment_audit
    ADD CONSTRAINT telegram_comment_audit_update_id_fkey FOREIGN KEY (update_id) REFERENCES public.telegram_inbound_updates(update_id);


--

-- Name: ai_analyses ai analyses owner can insert; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "ai analyses owner can insert" ON public.ai_analyses FOR INSERT TO authenticated WITH CHECK ((EXISTS ( SELECT 1
   FROM public.matters m
  WHERE ((m.id = ai_analyses.matter_id) AND (m.owner_user_id = (( SELECT auth.uid() AS uid))::text)))));


--

-- Name: ai_analyses ai analyses owner can read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "ai analyses owner can read" ON public.ai_analyses FOR SELECT TO authenticated USING ((EXISTS ( SELECT 1
   FROM public.matters m
  WHERE ((m.id = ai_analyses.matter_id) AND (m.owner_user_id = (( SELECT auth.uid() AS uid))::text)))));


--

-- Name: ai_analyses; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.ai_analyses ENABLE ROW LEVEL SECURITY;

--

-- Name: audit_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.audit_events ENABLE ROW LEVEL SECURITY;

--

-- Name: case_events authenticated users can manage case events; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "authenticated users can manage case events" ON public.case_events TO authenticated USING (true) WITH CHECK (true);


--

-- Name: case_tasks authenticated users can manage case tasks; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "authenticated users can manage case tasks" ON public.case_tasks TO authenticated USING (true) WITH CHECK (true);


--

-- Name: cases authenticated users can manage cases; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "authenticated users can manage cases" ON public.cases TO authenticated USING (true) WITH CHECK (true);


--

-- Name: case_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.case_events ENABLE ROW LEVEL SECURITY;

--

-- Name: case_graph_evidence; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.case_graph_evidence ENABLE ROW LEVEL SECURITY;

--

-- Name: case_graph_evidence case_graph_evidence_service_access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY case_graph_evidence_service_access ON public.case_graph_evidence TO service_role USING (true) WITH CHECK (true);


--

-- Name: case_graph_people; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.case_graph_people ENABLE ROW LEVEL SECURITY;

--

-- Name: case_graph_people case_graph_people_service_access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY case_graph_people_service_access ON public.case_graph_people TO service_role USING (true) WITH CHECK (true);


--

-- Name: case_graph_timeline; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.case_graph_timeline ENABLE ROW LEVEL SECURITY;

--

-- Name: case_graph_timeline case_graph_timeline_service_access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY case_graph_timeline_service_access ON public.case_graph_timeline TO service_role USING (true) WITH CHECK (true);


--

-- Name: case_tasks; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.case_tasks ENABLE ROW LEVEL SECURITY;

--

-- Name: cases; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.cases ENABLE ROW LEVEL SECURITY;

--

-- Name: clients; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.clients ENABLE ROW LEVEL SECURITY;

--

-- Name: deadlines; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.deadlines ENABLE ROW LEVEL SECURITY;

--

-- Name: deadlines deadlines owner can insert; Type: POLICY; Schema: public; Owner: -
--



--

-- Name: deadlines deadlines owner can read; Type: POLICY; Schema: public; Owner: -
--



--

-- Name: deadlines deadlines owner can update; Type: POLICY; Schema: public; Owner: -
--



--

-- Name: document_chunks document chunks owner can insert; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "document chunks owner can insert" ON public.document_chunks FOR INSERT TO authenticated WITH CHECK ((EXISTS ( SELECT 1
   FROM (public.documents d
     JOIN public.matters m ON ((m.id = d.matter_id)))
  WHERE ((d.id = document_chunks.document_id) AND (m.owner_user_id = (( SELECT auth.uid() AS uid))::text)))));


--

-- Name: document_chunks document chunks owner can read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "document chunks owner can read" ON public.document_chunks FOR SELECT TO authenticated USING ((EXISTS ( SELECT 1
   FROM (public.documents d
     JOIN public.matters m ON ((m.id = d.matter_id)))
  WHERE ((d.id = document_chunks.document_id) AND (m.owner_user_id = (( SELECT auth.uid() AS uid))::text)))));


--

-- Name: document_chunks; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.document_chunks ENABLE ROW LEVEL SECURITY;

--

-- Name: document_ocr_jobs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.document_ocr_jobs ENABLE ROW LEVEL SECURITY;

--

-- Name: document_pages; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.document_pages ENABLE ROW LEVEL SECURITY;

--

-- Name: document_pipeline_jobs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.document_pipeline_jobs ENABLE ROW LEVEL SECURITY;

--

-- Name: document_recovery_jobs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.document_recovery_jobs ENABLE ROW LEVEL SECURITY;

--

-- Name: documents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

--

-- Name: documents documents owner can insert; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "documents owner can insert" ON public.documents FOR INSERT TO authenticated WITH CHECK ((EXISTS ( SELECT 1
   FROM public.matters m
  WHERE ((m.id = documents.matter_id) AND (m.owner_user_id = (( SELECT auth.uid() AS uid))::text)))));


--

-- Name: documents documents owner can read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "documents owner can read" ON public.documents FOR SELECT TO authenticated USING ((EXISTS ( SELECT 1
   FROM public.matters m
  WHERE ((m.id = documents.matter_id) AND (m.owner_user_id = (( SELECT auth.uid() AS uid))::text)))));


--

-- Name: documents documents owner can update; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "documents owner can update" ON public.documents FOR UPDATE TO authenticated USING ((EXISTS ( SELECT 1
   FROM public.matters m
  WHERE ((m.id = documents.matter_id) AND (m.owner_user_id = (( SELECT auth.uid() AS uid))::text))))) WITH CHECK ((EXISTS ( SELECT 1
   FROM public.matters m
  WHERE ((m.id = documents.matter_id) AND (m.owner_user_id = (( SELECT auth.uid() AS uid))::text)))));


--

-- Name: emails; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.emails ENABLE ROW LEVEL SECURITY;

--

-- Name: entity_investigation_sources; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.entity_investigation_sources ENABLE ROW LEVEL SECURITY;

--

-- Name: entity_investigations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.entity_investigations ENABLE ROW LEVEL SECURITY;

--

-- Name: entity_investigations entity_investigations_service_access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY entity_investigations_service_access ON public.entity_investigations TO service_role USING (true) WITH CHECK (true);


--

-- Name: entity_investigation_sources entity_sources_service_access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY entity_sources_service_access ON public.entity_investigation_sources TO service_role USING (true) WITH CHECK (true);


--

-- Name: jafar_audit_trail jafar_audit_service_access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY jafar_audit_service_access ON public.jafar_audit_trail TO service_role USING (true) WITH CHECK (true);


--

-- Name: jafar_audit_trail; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.jafar_audit_trail ENABLE ROW LEVEL SECURITY;

--

-- Name: legal_audit_log; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.legal_audit_log ENABLE ROW LEVEL SECURITY;

--

-- Name: legal_case_entities; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.legal_case_entities ENABLE ROW LEVEL SECURITY;

--

-- Name: legal_case_entities legal_case_entities_service_access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY legal_case_entities_service_access ON public.legal_case_entities TO service_role USING (true) WITH CHECK (true);


--

-- Name: legal_entities; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.legal_entities ENABLE ROW LEVEL SECURITY;

--

-- Name: legal_entities legal_entities_service_access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY legal_entities_service_access ON public.legal_entities TO service_role USING (true) WITH CHECK (true);


--

-- Name: legal_entity_case_links; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.legal_entity_case_links ENABLE ROW LEVEL SECURITY;

--

-- Name: legal_entity_case_links legal_entity_case_links_service_access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY legal_entity_case_links_service_access ON public.legal_entity_case_links TO service_role USING (true) WITH CHECK (true);


--

-- Name: legal_entity_research_audit; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.legal_entity_research_audit ENABLE ROW LEVEL SECURITY;

--

-- Name: legal_entity_research_audit legal_entity_research_audit_service_access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY legal_entity_research_audit_service_access ON public.legal_entity_research_audit TO service_role USING (true) WITH CHECK (true);


--

-- Name: legal_entity_research_runs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.legal_entity_research_runs ENABLE ROW LEVEL SECURITY;

--

-- Name: legal_entity_research_runs legal_entity_research_runs_service_access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY legal_entity_research_runs_service_access ON public.legal_entity_research_runs TO service_role USING (true) WITH CHECK (true);


--

-- Name: legal_entity_research_sources; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.legal_entity_research_sources ENABLE ROW LEVEL SECURITY;

--

-- Name: legal_entity_research_sources legal_entity_research_sources_read; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY legal_entity_research_sources_read ON public.legal_entity_research_sources FOR SELECT TO authenticated USING ((enabled = true));


--

-- Name: legal_entity_source_checks; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.legal_entity_source_checks ENABLE ROW LEVEL SECURITY;

--

-- Name: legal_entity_source_checks legal_entity_source_checks_service_access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY legal_entity_source_checks_service_access ON public.legal_entity_source_checks TO service_role USING (true) WITH CHECK (true);


--

-- Name: legal_entity_source_results; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.legal_entity_source_results ENABLE ROW LEVEL SECURITY;

--

-- Name: legal_entity_source_results legal_entity_source_results_service_access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY legal_entity_source_results_service_access ON public.legal_entity_source_results TO service_role USING (true) WITH CHECK (true);


--

-- Name: matter_events matter events owner can insert; Type: POLICY; Schema: public; Owner: -
--



--

-- Name: matter_events matter events owner can read; Type: POLICY; Schema: public; Owner: -
--



--

-- Name: matter_events matter events owner can update; Type: POLICY; Schema: public; Owner: -
--



--

-- Name: matter_aliases; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.matter_aliases ENABLE ROW LEVEL SECURITY;

--

-- Name: matter_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.matter_events ENABLE ROW LEVEL SECURITY;

--

-- Name: matters; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.matters ENABLE ROW LEVEL SECURITY;

--

-- Name: matters matters owner can insert; Type: POLICY; Schema: public; Owner: -
--



--

-- Name: matters matters owner can read; Type: POLICY; Schema: public; Owner: -
--



--

-- Name: matters matters owner can update; Type: POLICY; Schema: public; Owner: -
--



--

-- Name: recovery_worker_incidents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.recovery_worker_incidents ENABLE ROW LEVEL SECURITY;

--

-- Name: recovery_worker_runs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.recovery_worker_runs ENABLE ROW LEVEL SECURITY;

--

-- Name: sync_metadata sync metadata owner access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "sync metadata owner access" ON public.sync_metadata TO authenticated USING ((user_id = (( SELECT auth.uid() AS uid))::text)) WITH CHECK ((user_id = (( SELECT auth.uid() AS uid))::text));


--

-- Name: sync_conflicts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.sync_conflicts ENABLE ROW LEVEL SECURITY;

--

-- Name: sync_metadata; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.sync_metadata ENABLE ROW LEVEL SECURITY;

--

-- Name: telegram_approval_queue; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.telegram_approval_queue ENABLE ROW LEVEL SECURITY;

--

-- Name: telegram_approval_queue telegram_approval_queue_service_access; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY telegram_approval_queue_service_access ON public.telegram_approval_queue TO service_role USING (true) WITH CHECK (true);


--

-- Name: telegram_comment_audit; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.telegram_comment_audit ENABLE ROW LEVEL SECURITY;

--

-- Name: telegram_comment_queue; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.telegram_comment_queue ENABLE ROW LEVEL SECURITY;

--

-- Name: telegram_editorial_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.telegram_editorial_events ENABLE ROW LEVEL SECURITY;

--

-- Name: telegram_inbound_updates; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.telegram_inbound_updates ENABLE ROW LEVEL SECURITY;

--

-- Name: telegram_metrics_daily; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.telegram_metrics_daily ENABLE ROW LEVEL SECURITY;

--

-- Name: telegram_publications; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.telegram_publications ENABLE ROW LEVEL SECURITY;

--

-- Name: telegram_worker_runs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.telegram_worker_runs ENABLE ROW LEVEL SECURITY;

--

-- Name: worker_heartbeats; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.worker_heartbeats ENABLE ROW LEVEL SECURITY;

--

-- Name: supabase_realtime sync_metadata; Type: PUBLICATION TABLE; Schema: public; Owner: -
--

ALTER PUBLICATION supabase_realtime ADD TABLE ONLY public.sync_metadata;


--
