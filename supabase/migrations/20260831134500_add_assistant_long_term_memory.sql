create extension if not exists vector;

create table if not exists public.assistant_memories (
    id uuid primary key,
    owner_user_id uuid not null,
    matter_id uuid null references public.matters(id) on delete cascade,
    kind text not null check (kind in ('preference','decision','fact','workflow','note')),
    content text not null check (length(btrim(content)) > 0),
    source text null,
    confidence double precision not null default 1.0 check (confidence >= 0.0 and confidence <= 1.0),
    embedding vector(1536) not null,
    created_at timestamptz not null default now()
);

create index if not exists assistant_memories_owner_created_idx
    on public.assistant_memories(owner_user_id, created_at desc);

create index if not exists assistant_memories_owner_matter_idx
    on public.assistant_memories(owner_user_id, matter_id);

create index if not exists assistant_memories_embedding_hnsw_idx
    on public.assistant_memories using hnsw (embedding vector_cosine_ops);

alter table public.assistant_memories enable row level security;

revoke all on public.assistant_memories from anon, authenticated;
grant all on public.assistant_memories to service_role;

create or replace function public.match_assistant_memories(
    p_owner_user_id uuid,
    p_query_embedding vector(1536),
    p_matter_id uuid default null,
    p_match_count integer default 8,
    p_min_similarity double precision default 0.0
)
returns table (
    id uuid,
    owner_user_id uuid,
    matter_id uuid,
    kind text,
    content text,
    source text,
    confidence double precision,
    created_at timestamptz,
    similarity double precision
)
language sql
stable
security definer
set search_path = public
as $$
    select
        m.id,
        m.owner_user_id,
        m.matter_id,
        m.kind,
        m.content,
        m.source,
        m.confidence,
        m.created_at,
        1 - (m.embedding <=> p_query_embedding) as similarity
    from public.assistant_memories m
    where m.owner_user_id = p_owner_user_id
      and (p_matter_id is null or m.matter_id is null or m.matter_id = p_matter_id)
      and 1 - (m.embedding <=> p_query_embedding) >= p_min_similarity
    order by m.embedding <=> p_query_embedding
    limit greatest(1, least(p_match_count, 50));
$$;

revoke all on function public.match_assistant_memories(uuid, vector, uuid, integer, double precision) from public, anon, authenticated;
grant execute on function public.match_assistant_memories(uuid, vector, uuid, integer, double precision) to service_role;
