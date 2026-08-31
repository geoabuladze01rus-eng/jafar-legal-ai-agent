create extension if not exists vector;

do $$
declare
  embedding_type text;
begin
  select udt_name
  into embedding_type
  from information_schema.columns
  where table_schema = 'public'
    and table_name = 'document_chunks'
    and column_name = 'embedding';

  if embedding_type is null then
    raise exception 'document_chunks.embedding column is required for matter RAG';
  end if;

  if embedding_type <> 'vector' then
    raise exception 'document_chunks.embedding must use pgvector; found %', embedding_type;
  end if;
end
$$;

create index if not exists document_chunks_embedding_hnsw_idx
on public.document_chunks
using hnsw (embedding vector_cosine_ops)
where embedding is not null;

create index if not exists documents_matter_id_idx
on public.documents (matter_id);

create or replace function public.match_matter_document_chunks(
  p_matter_id text,
  p_owner_user_id text,
  p_query_embedding vector(1536),
  p_match_count integer default 8,
  p_min_similarity double precision default 0
)
returns table (
  chunk_id text,
  document_id text,
  matter_id text,
  source_page integer,
  chunk_index integer,
  content text,
  similarity double precision
)
language sql
stable
security invoker
set search_path = public, extensions
as $$
  select
    c.id::text as chunk_id,
    c.document_id::text as document_id,
    d.matter_id::text as matter_id,
    c.source_page,
    c.chunk_index,
    c.content,
    1 - (c.embedding <=> p_query_embedding) as similarity
  from public.document_chunks c
  join public.documents d on d.id = c.document_id
  join public.matters m on m.id = d.matter_id
  where d.matter_id::text = p_matter_id
    and m.owner_user_id::text = p_owner_user_id
    and c.embedding is not null
    and 1 - (c.embedding <=> p_query_embedding) >= p_min_similarity
  order by c.embedding <=> p_query_embedding
  limit greatest(1, least(coalesce(p_match_count, 8), 50));
$$;

revoke all on function public.match_matter_document_chunks(text, text, vector, integer, double precision) from public;
revoke all on function public.match_matter_document_chunks(text, text, vector, integer, double precision) from anon;
revoke all on function public.match_matter_document_chunks(text, text, vector, integer, double precision) from authenticated;
grant execute on function public.match_matter_document_chunks(text, text, vector, integer, double precision) to service_role;
