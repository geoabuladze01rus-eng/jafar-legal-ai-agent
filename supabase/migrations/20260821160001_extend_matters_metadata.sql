alter table public.matters
  add column if not exists metadata jsonb not null default '{}'::jsonb;
