create table if not exists public.matter_intelligence_records (
    id text primary key,
    owner_id text not null,
    -- Matter rows are owned by the application repository; this schema is additive and
    -- does not assume a particular legacy matter table name.
    matter_id text not null,
    kind text not null check (kind in ('evidence','contradiction','authority','council','position','hearing')),
    payload jsonb not null check (jsonb_typeof(payload) = 'object'),
    analysis_run_id text not null check (length(analysis_run_id) between 1 and 200),
    version integer not null check (version > 0),
    fingerprint text not null unique,
    created_at timestamptz not null default now()
);

create index if not exists matter_intelligence_records_owner_matter_kind_idx
    on public.matter_intelligence_records(owner_id, matter_id, kind, created_at desc);
alter table public.matter_intelligence_records enable row level security;
revoke all on public.matter_intelligence_records from public, anon, authenticated;
grant select, insert on public.matter_intelligence_records to service_role;

create or replace function public.prevent_matter_intelligence_record_mutation()
returns trigger language plpgsql set search_path = public, pg_catalog as $$
begin
  raise exception 'matter_intelligence_records_are_append_only';
end;
$$;
drop trigger if exists matter_intelligence_records_immutable on public.matter_intelligence_records;
create trigger matter_intelligence_records_immutable
before update or delete on public.matter_intelligence_records
for each row execute function public.prevent_matter_intelligence_record_mutation();
revoke all on function public.prevent_matter_intelligence_record_mutation() from public, anon, authenticated;
