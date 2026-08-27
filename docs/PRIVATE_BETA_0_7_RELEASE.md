# Jafar Private Beta 0.7 — finalization record

Date: 2026-08-27

Finalization branch: `codex/private-beta-0.7-finalize`

PR base: `release/jafar-private-beta-0.7`

## Consolidated baseline

The branch starts from `codex/local-backend-autostart` at `15d8d7b`, which already contains the
canonical Pavlik/legal core, Apple local-backend autostart, and merged Gmail read-only gateway. It
also merges the release-record commit from `release/jafar-private-beta-0.7` so the divergence is
explicit and auditable. Neither `main` nor production is part of this finalization.

Included Private Beta scope:

- legal analysis, matter lifecycle, provenance-aware PDF/DOCX/TXT/Markdown intake;
- Pavlik acceptance, extension-motion, evidence-gap, and private harness contracts;
- authenticated FastAPI command surface and review-only consequential actions;
- Apple macOS/iOS command client, voice path, Keychain API key, and local backend autostart;
- Outlook list/read pipeline and tested Microsoft Graph read-only adapter;
- Gmail installed-app OAuth with exact `gmail.readonly`, Keychain credentials, list/get-only API,
  bounded snippets, and metadata-only link/attachment handling;
- Supabase ACL hardening migration staged for isolated validation only, never applied here.

## Final verification snapshot

- Ruff: **PASS**;
- full pytest: **218 passed, 1 known non-blocking warning**;
- focused API/command/Gmail/Outlook/Pavlik/legal-document suite: **45 passed, 1 warning**;
- normal wheel install and package/API version `0.7.0`: **PASS**;
- synthetic Gmail HTTP command E2E without credentials: **PASS**;
- macOS Debug build with signing disabled: **PASS**;
- iOS Simulator Debug build with signing disabled: **PASS**;
- local backend interrupt/child-process cleanup: **PASS**;
- tracked-file secret scan and diff whitespace check: **PASS**.

The warning is the existing Starlette/httpx TestClient deprecation and is not a legal, privacy, or
runtime correctness failure.

## Security changes in finalization

- Missing API configuration now fails closed in every environment. Unauthenticated development
  requires the explicit local-only `ALLOW_UNAUTHENTICATED_DEVELOPMENT=true` opt-in.
- Apple backend output is parsed as buffered complete lines, avoiding split secret/endpoint records.
- Failure to persist the ephemeral API key stops the spawned backend instead of orphaning it.
- App termination synchronously interrupts the helper; its cleanup path terminates the child server.
- Package, module, and FastAPI versions are aligned at `0.7.0`.
- The reviewed Supabase `TRUNCATE` revocation is present as an unapplied migration and requires an
  isolated staging gate before any separately approved production action.

## Immutable safety boundary

- no Gmail or Outlook send, modify, label, move, archive, trash, or delete operation;
- no Gmail attachment-body fetch and no automatic external-link opening;
- no autonomous legal filing, publication, Telegram legal reply, or other consequential action;
- external AI remains disabled by default;
- no credentials, tokens, API keys, mailbox content, or private client material in Git;
- no deployment, production Supabase mutation, merge to `main`, or release-PR promotion is
  authorized by this record.

## Owner-controlled Gmail gate

The owner-Mac live OAuth and macOS command round trip passed previously on 2026-08-27. Finalization
did not read Gmail or reuse, print, or inspect those credentials; the release gate was repeated with
synthetic data only. New installations still require the owner to create a Google OAuth **Desktop
app** client, authorize exactly `gmail.readonly`, and keep the downloaded JSON outside the repository.
No billing account or card is required for this local testing flow.

## Deferred/non-blocking items

- Two legacy, currently unreferenced mail/inbox abstractions remain for a later focused cleanup;
  removing them during release consolidation would add unnecessary regression risk.
- GitHub Actions infrastructure status is separate from the verified local gates.
- Supabase ACL/RPC/worker validation remains mandatory in an isolated environment before production.
- Draft PR review and merge decisions remain owner-controlled.
