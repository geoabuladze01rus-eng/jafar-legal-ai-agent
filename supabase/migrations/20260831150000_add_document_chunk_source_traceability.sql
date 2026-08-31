alter table public.document_chunks
  add column if not exists stable_chunk_id text,
  add column if not exists source_section text,
  add column if not exists source_start integer,
  add column if not exists source_end integer;

create unique index if not exists document_chunks_document_stable_chunk_id_idx
  on public.document_chunks (document_id, stable_chunk_id)
  where stable_chunk_id is not null;
