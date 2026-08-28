# Email analysis persistence RPC v2 RFC

Status: READY_FOR_LOCAL_IMPLEMENTATION. Design only; no migration or production change is included.

## Problem and verified V1 behavior

`public.persist_email_processing(jsonb)` returns `void`, inserts `public.documents` with a generated UUID, and does not insert `public.ai_analyses` or return the document UUID. The caller is `SupabaseProcessingResultStore.save` (`src/jafar/processing_persistence.py`).

## Decision

Create versioned `public.persist_email_processing_v2(jsonb)` and keep V1 during rollout. A new signature avoids PostgreSQL return-type replacement hazards and protects unknown callers.

## Input

```json
{"message_id":"...","documents":[{"filename":"...","content_type":"...","storage_path":"...","processing_status":"stored","matter_id":"<trusted UUID>","analysis":{"result":{},"source_chunks":[]}}]}
```

The server must validate the Matter UUID and derive the new document UUID internally. The caller never supplies a document UUID for a newly created document.

## Output

```json
{"status":"ok","documents":[{"document_id":"<UUID>","analysis_id":"<UUID|null>","matter_id":"<UUID|null>"}]}
```

No text, OCR, embeddings, storage paths, signed URLs or secrets are returned.

## Atomic modes

Matter-addressable mode inserts the document, captures `RETURNING id`, then inserts `ai_analyses` with the same `matter_id` and document UUID. Any failure aborts the function transaction. Unmatched mode may insert the document with null matter and must not create an addressable analysis.

## Analysis mapping

Required existing columns: `matter_id`, `document_id`, `result`, `source_chunks`, `requires_lawyer_review`, `review_status`; defaults remain authoritative. `result.missing_information` is preserved. Initial review is `pending`/requires lawyer review; never auto-approved. `source_chunks` remain analysis-level (P2), not copied to individual gaps.

## Security and RLS

`SECURITY DEFINER SET search_path = public`; explicitly `REVOKE EXECUTE ... FROM PUBLIC, anon, authenticated` and `GRANT EXECUTE ... TO service_role`. Existing table RLS remains unchanged; client roles cannot execute the mutation RPC or directly write analysis rows.

## SQL draft (NOT APPLIED)

```sql
CREATE FUNCTION public.persist_email_processing_v2(p_payload jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_doc jsonb; v_document_id uuid; v_analysis_id uuid; v_matter_id uuid; v_out jsonb = '[]'::jsonb;
BEGIN
  -- preserve V1 email validation and processing writes;
  -- for each document: validate trusted matter_id, INSERT documents ... RETURNING id,
  -- optionally INSERT ai_analyses(matter_id, document_id, result, source_chunks,
  -- requires_lawyer_review, review_status) ... RETURNING id;
  -- append only IDs to v_out and return jsonb_build_object('status','ok','documents',v_out).
END; $$;
REVOKE EXECUTE ON FUNCTION public.persist_email_processing_v2(jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.persist_email_processing_v2(jsonb) TO service_role;
```

The comments intentionally leave table-specific email writes to implementation after local contract tests; this RFC is not executable SQL.

## Caller, rollout and rollback

`SupabaseProcessingResultStore.save` should call V2, parse and validate returned UUIDs, and never reconstruct IDs. Roll out V2, validate locally, switch the caller, retain V1 until all callers are inventoried, and roll back by reverting the caller to V1. Do not delete valid rows during rollback.

## Idempotency and threats

Use the existing message/fingerprint idempotency contract; implementation must define a deterministic retry key before migration. Threats include spoofed Matter IDs, cross-matter documents, malformed JSON, replay, duplicate analysis, privilege escalation and unsafe search paths. Mitigations are server-side Matter validation, deriving document IDs internally, atomic transaction rollback, explicit role grants, fixed search path, and unique retry handling.

## Acceptance plan

Local disposable DB tests must prove document/analysis IDs, same-matter invariant, rollback, unmatched behavior, duplicate retry behavior, result preservation, review safety, and PUBLIC/anon/authenticated denial with service-role execution. Production migration status remains NOT APPLIED.

## Identity decision (package #20 forensic review)

The only runtime persistence caller is `SupabaseProcessingResultStore.save`. The
provider attachment object has `attachment_id`, but `InboxDocumentResult` drops it
before persistence. `message_id` survives, but is message-scoped and cannot
distinguish two attachments. The only persisted-looking fingerprint is not a safe
source identity: `ExtractedDocument.fingerprint` is SHA-256 of normalized extracted
text plus media type (not the raw bytes), while the raw-byte SHA-256 in
`InboxProcessor` is a local value and is not persisted. Filename, storage path and
timestamps are mutable/ambiguous. No upstream processing key is created once and
reused across process restarts.

The domain path now preserves provider, message ID and attachment ID on each
`InboxAttachment`/`InboxDocumentResult` and exposes a deterministic processing key
at the persistence boundary. Providers without an attachment ID remain explicitly
ineligible (`None` identity); no filename/fingerprint fallback exists. The selected
strategy is therefore **D1** for Gmail attachments with an ID.

### Required V2 contract once the blocker is resolved

* Source artifact identity is `(provider, message_id, provider_attachment_id)`.
  It is distinct from the database `documents.id`; the provider namespace is
  mandatory because provider IDs are not globally unique.
* `document_processing_key` is a structured, canonical representation of that
  tuple (prefer a dedicated column or a hash of canonical JSON, never ambiguous
  string concatenation). A first processing creates one document; an exact retry
  reuses it. Two attachments in one message remain distinct, including equal
  filenames. Identical bytes in different messages remain distinct source events.
* `analysis_run_id` is generated by the server workflow before the first
  persistence attempt and is stored/recovered with the durable job. Technical
  retries reuse it; an explicit re-analysis receives a new UUID and may create a
  second `ai_analyses` row for the same document. It is never derived from text or
  a timestamp and is not an authorization mechanism.
* The database must enforce uniqueness transactionally (unique processing key and
  unique analysis run ID, with `ON CONFLICT`/equivalent returning the existing
  IDs). Application-level check-then-insert is insufficient for concurrent
  retries. Legacy rows without the new keys remain legacy via partial unique
  indexes; no destructive backfill is required.
* Matter authorization remains server-side and independent of idempotency. A
  caller-supplied or spoofed Matter UUID cannot grant access. The RPC remains
  `SECURITY DEFINER`, fixed `search_path`, service-role only; no client execution.

### Retry and replay semantics

I1 first call creates one document and one initial analysis; I2/I3 exact retry or
10x replay returns the same IDs; I4 concurrent duplicate yields one logical pair;
I5 intentional re-analysis uses the same document and a new analysis ID; I6/I7
second or same-named attachment creates a different document; I8 same bytes in a
different message creates a different document; I9 unmatched mail creates no
fabricated Matter analysis; I10 spoofed Matter is rejected; I11 malformed identity
rolls back atomically; I12 only service-role can execute.

V1 side effects remain unchanged during rollout. V2 may return richer IDs, but must
not silently alter existing email persistence or failure semantics. No migration,
RPC change, production write, or real-email processing is part of this RFC.

## Caller and side-effect forensics

Repository-wide search finds one runtime caller: `SupabaseProcessingResultStore.save` in `src/jafar/processing_persistence.py`, which ignores the RPC return value and calls `persist_email_processing` once per processing result. Tests and migrations are non-runtime references. V1 writes an email processing record through the RPC's surrounding contract and inserts one `documents` row per payload document; the function returns no IDs and has no `ON CONFLICT` or document deduplication.

The stable logical input identifier is the inbound `message_id`; attachment fingerprints remain metadata, not database identity. The current documents table still has no DB-enforced uniqueness and V1 remains I4, but the application source identity is now durable across reconstruction; DB enforcement is future V2 work.

V1 must remain unchanged. V2 may return richer IDs and extend payload semantics, but must preserve V1 side effects and failure behavior. Byte-for-byte payload compatibility is not required for a versioned function; side-effect compatibility is required. Retry and intentional re-analysis must use distinct explicit identities, never timestamps, filenames, storage paths or heuristics.
