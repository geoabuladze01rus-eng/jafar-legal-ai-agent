-- Recreate the service-only RPC after the source-traceability columns exist.
-- The prior 12:30 migration remains valid for databases replaying the full history.
drop function if exists public.match_matter_document_chunks(
  text,
  text,
  vector,
  integer,
  double precision
);

create function public.match_matter_document_chunks(
  p_matter_id text,
  p_owner_user_id text,
  p_query_embedding vector(1536),
  p_match_count integer default 8,
  p_min_similarity double precision default 0.01
)
returns table (
  chunk_id text,
  stable_chunk_id text,
  document_id text,
  matter_id text,
  owner_user_id text,
  source_page integer,
  source_section text,
  source_start integer,
  source_end integer,
  chunk_index integer,
  content text,
  similarity double precision
)
language sql
stable
security invoker
set search_path = public, extensions
set hnsw.iterative_scan = strict_order
as $$
  select
    c.id::text as chunk_id,
    c.stable_chunk_id,
    c.document_id::text as document_id,
    d.matter_id::text as matter_id,
    m.owner_user_id::text as owner_user_id,
    c.source_page,
    c.source_section,
    c.source_start,
    c.source_end,
    c.chunk_index,
    c.content,
    1 - (c.embedding <=> p_query_embedding) as similarity
  from public.document_chunks c
  join public.documents d on d.id = c.document_id
  join public.matters m on m.id = d.matter_id
  where nullif(btrim(p_matter_id), '') is not null
    and nullif(btrim(p_owner_user_id), '') is not null
    and d.matter_id::text = p_matter_id
    and m.owner_user_id::text = p_owner_user_id
    and c.embedding is not null
    and 1 - (c.embedding <=> p_query_embedding) >= least(
      greatest(coalesce(p_min_similarity, 0.01), 0.0),
      1.0
    )
  order by
    c.embedding <=> p_query_embedding,
    c.document_id,
    c.source_page,
    coalesce(c.stable_chunk_id, c.id::text),
    c.chunk_index
  limit least(greatest(coalesce(p_match_count, 8), 0), 200);
$$;

revoke all on function public.match_matter_document_chunks(
  text,
  text,
  vector,
  integer,
  double precision
) from public;
revoke all on function public.match_matter_document_chunks(
  text,
  text,
  vector,
  integer,
  double precision
) from anon;
revoke all on function public.match_matter_document_chunks(
  text,
  text,
  vector,
  integer,
  double precision
) from authenticated;
grant execute on function public.match_matter_document_chunks(
  text,
  text,
  vector,
  integer,
  double precision
) to service_role;
