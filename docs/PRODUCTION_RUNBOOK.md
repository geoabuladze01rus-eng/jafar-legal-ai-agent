# Jafar production-readiness runbook

This runbook is for a non-production Supabase project or development branch.
Never start with production. Deploy only from the tested
`codex/jafar-canonical-v2` branch after confirming that its current `HEAD` is a
descendant of the recorded `origin/main` base. Recovery-only commits and roots
must not be present in that branch's ancestry.

## Document state machine

```text
queued/stored
  -> ocr_processing
  -> ocr_completed
  -> pipeline_processing
  -> chunk completed
  -> embed completed
  -> analyze completed
  -> completed
```

`manual_review` and `failed` are terminal until an explicit, audited recovery
action. OCR completion alone never sets the document to `completed`.

The OCR completion transaction calls `complete_ocr_and_enqueue_pipeline` and
atomically creates the unique `chunk`, `embed`, and `analyze` jobs. Claims are
lease-fenced and use `FOR UPDATE SKIP LOCKED`. Analyze is not claimable until
chunk and embed are complete, at least one chunk exists, and every chunk has an
embedding.

## Authentication and secrets

Gateway authentication and worker authentication are deliberately separate:

- Supabase gateway header: `apikey`, populated from `supabase_publishable_key`.
- Worker header: `x-jafar-worker-secret`, compared only with
  `JAFAR_WORKER_SECRET`.
- Database access inside an Edge Function: `SUPABASE_SERVICE_ROLE_KEY`.

Required secret/configuration names are:

- `project_url`
- `supabase_publishable_key`
- `jafar_worker_secret`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `JAFAR_WORKER_SECRET`
- `OPENAI_API_KEY`
- `JAFAR_OCR_MODEL`
- `JAFAR_ANALYSIS_MODEL`
- `JAFAR_EMBEDDING_MODEL`
- `JAFAR_OPENAI_MAX_ATTEMPTS`
- `JAFAR_OPENAI_TIMEOUT_MS`
- `JAFAR_EMBEDDING_BATCH_SIZE`
- `JAFAR_ANALYSIS_MAX_CONTEXT_CHARS`

Do not put values in Git, migrations, test fixtures, command history, or logs.
The workers intentionally use `verify_jwt = false`: the scheduler supplies the
publishable gateway key and the function performs constant-time validation of
the dedicated worker secret.

## Retry policy

OpenAI requests retry only network errors, timeouts, HTTP 408, 409, 429, and
5xx. They do not retry HTTP 400, 401, 403, 404, malformed structured output, or
non-recoverable schema errors. Attempts are bounded and use capped exponential
backoff with jitter; `Retry-After` is honored.

Transient stage failure calls `retry_document_pipeline_job`, which atomically
sets `queued`, calculates `available_at`, and clears all lease fields. Permanent
failure becomes `failed` or `manual_review`. Expired leases are recovered while
the document retry limit permits. A successful partial embedding batch uses
`resume_document_embedding_job`, so processing another batch does not spend the
failure retry budget. Existing embeddings are never overwritten.

## Staging deployment checklist

1. Record the current `origin/main` SHA and the tested
   `codex/jafar-canonical-v2` SHA. Confirm ancestry with
   `git merge-base --is-ancestor origin/main HEAD`.
2. Confirm the canonical branch passes Python, Ruff, Deno, migration parse, and
   secret-scan gates, and that no recovery-only root is in its ancestry.
3. Create or select an isolated Supabase staging project/branch. If branch
   creation is billable, obtain cost approval first.
4. Take a schema backup and record the current migrations, function versions,
   cron jobs, Vault secret names, and Edge Function versions. Do not print
   secret values.
5. Apply, in order:
   - `20260825010000_harden_document_pipeline_end_to_end.sql`
   - `20260825011000_separate_document_worker_auth.sql`
   - `20260825012000_add_document_pipeline_retry_scheduling.sql`
   - `20260825013000_preserve_embedding_resume_retry_budget.sql`
6. Provision the required Vault/Edge Function secret names through the approved
   secret manager.
7. Deploy `document-ocr-worker-v4` and `document-pipeline-worker-v3` from the
   same tested commit. Do not deploy the workers before their RPCs.
8. Run the database pgTAP suite and all local Python/Deno checks from that
   commit.
9. Invoke `schedule_jafar_document_workers()` only after all three scheduler
   Vault names exist. Confirm exactly one OCR and one pipeline cron job.
10. Run the synthetic E2E below, inspect redacted request logs and heartbeats,
    and keep the project isolated until every expected state is observed.

## Synthetic legal-document E2E

Use only `tests/fixtures/synthetic_legal_document.pdf.b64` and its `.txt` OCR
sidecar. Both describe fictional people and a fictional case.

Automated deterministic coverage:

```bash
PYTHONPATH=src pytest tests/test_synthetic_legal_document_e2e.py -q
deno test --allow-env supabase/functions/_shared/document-worker_test.ts
```

The Python test validates PDF ingest, mocked OCR normalization, case/date/risk
extraction, contradiction text, and the missing referenced attachment. The Deno
test validates chunk creation, mocked embedding completion, citations for facts
and attributed statements, contradiction provenance, an evidence-gap citation,
and mandatory lawyer review.

Staging smoke procedure:

1. Decode the fixture outside the repository into a temporary file and upload it
   to the private `jafar-legal-documents` bucket.
2. Create a test document through the normal authenticated ingest path. Record
   its generated document ID; never use a production document.
3. For a deterministic run, configure the approved mock provider or inject the
   fixture sidecar as the OCR test result. Do not weaken worker authentication.
4. Trigger the canonical OCR worker once. Confirm OCR job `completed`, document
   `pipeline_processing`, and exactly one queued job for each pipeline stage.
5. Trigger pipeline workers until idle. For a separate 250-chunk fixture,
   confirm embed progress `100 -> queued`, `100 -> queued`, `50 -> completed`.
6. Confirm analyze was not claimed before all embeddings existed.
7. Inspect the final analysis: every significant finding must resolve to the
   same document, page, chunk index, and source chunk; confidence must be within
   0..1; the missing attachment must remain an evidence gap; lawyer review must
   be required.
8. Repeat OCR completion and worker invocations. Confirm no duplicate jobs,
   chunks, terminal analyses, or overwritten embeddings.
9. Simulate one expired lease and one mocked 429/timeout. Confirm recovery and
   bounded requeue, then restore the normal test provider.
10. Delete only the isolated synthetic staging records through the approved
    cleanup workflow. Preserve audit evidence required for the release record.

## Recovery and rollback

These migrations are forward-oriented and intentionally avoid destructive DDL.
If staging fails, first pause both canonical cron jobs, then redeploy the prior
Edge Function versions. Leave additive columns and RPCs in place unless a
reviewed forward migration revokes/replaces them; dropping them while workers
are active can break leases. Restore the database from the staging backup only
when a data-level rollback is required. Never improvise a production down
migration.

## Client and connector launch gates

Apple/voice currently has platform-neutral contracts, device allow-listing,
authentication flags, and approval gates. It does not yet have a reviewed native
Mac/iPhone/iPad client, production identity/session handling, biometric
confirmation, secure Keychain storage, push delivery, accessibility validation,
or device-level E2E tests.

Email has Gmail and Outlook ingestion boundaries, attachment normalization,
deduplication, analysis, review-only drafts, and persistence contracts. Launch
still needs production OAuth consent/configuration, token rotation/revocation,
webhook or delta-sync reliability, provider-specific pagination/attachments,
Drive integration, calendar write approval, tenant isolation, and sandbox E2E.
No real account should be connected before those controls are reviewed.

Telegram has inbound normalization, classification, an audit record, editorial
safety, approval-first legal-help handling, and a fail-closed production guard.
Launch still needs durable publication/approval/comment queues, authenticated
reviewer identity, idempotent outbound delivery, scheduler ownership, rate-limit
handling, webhook verification, audit retention, and a controlled sandbox run.
Real publishing remains disabled until those gates pass.

## Release invariants

- No legal response is sent without the applicable human approval.
- No external system is modified silently.
- Facts, attributed statements, model inference, risks, contradictions, missing
  information, and evidence gaps remain distinct.
- Significant findings require document/page/chunk provenance.
- Confidential source content is sent only to an approved provider and never
  appears in operational logs.
- Every external action has an auditable proposal, approval, and result.
- Every document analysis remains explicitly subject to lawyer review.
