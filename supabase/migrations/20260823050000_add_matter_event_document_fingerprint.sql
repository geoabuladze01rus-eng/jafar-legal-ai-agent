alter table public.matter_events
  add column if not exists document_fingerprint text;

create unique index if not exists matter_events_matter_document_fingerprint_uidx
  on public.matter_events (matter_id, document_fingerprint)
  where document_fingerprint is not null;

alter table public.matter_events enable row level security;
