create table if not exists public.matter_events (
  id uuid primary key default gen_random_uuid(),
  matter_id uuid not null references public.matters(id) on delete cascade,
  owner_user_id text,
  title text not null,
  event_date timestamptz not null,
  description text,
  source_document text,
  created_at timestamptz not null default now()
);

create index if not exists matter_events_matter_id_event_date_idx
  on public.matter_events (matter_id, event_date desc);

alter table public.matter_events enable row level security;

create policy "matter events owner can read"
  on public.matter_events for select
  to authenticated
  using (owner_user_id = (select auth.uid()::text));

create policy "matter events owner can insert"
  on public.matter_events for insert
  to authenticated
  with check (owner_user_id = (select auth.uid()::text));

create policy "matter events owner can update"
  on public.matter_events for update
  to authenticated
  using (owner_user_id = (select auth.uid()::text))
  with check (owner_user_id = (select auth.uid()::text));
