# Jafar Private Beta 0.7 readiness — 2026-08-27

## Executive status

**Owner-local release candidate: PASS.** The consolidated release line is ready for Draft PR review.
This is not a production-readiness declaration and does not authorize a merge, deployment, mailbox
mutation, external legal action, or Supabase production change.

## Verified control point

- package, module, and FastAPI version: `0.7.0`;
- Ruff: **PASS**;
- full pytest: **218 passed, 1 known deprecation warning**;
- critical API/command/Gmail/Outlook/Pavlik/document subset: **45 passed**;
- normal wheel installation and `import jafar` without `PYTHONPATH`: **PASS**;
- synthetic Gmail HTTP command E2E, without OAuth credentials or a live account: **PASS**;
- macOS and iOS Simulator Debug builds, signing disabled: **PASS**;
- Apple helper interrupt and backend child cleanup: **PASS**;
- real Pavlik private E2E: previously **PASS**; private material was not used in finalization;
- owner-Mac Gmail OAuth/runtime/UI gate: previously **PASS**; not rerun in finalization;
- `main`, deployment, production Supabase, and live mailbox state: **UNTOUCHED**.

The only test warning is the existing Starlette/httpx TestClient deprecation.

## Readiness by subsystem

| Subsystem | Status | Boundary |
| --- | --- | --- |
| Legal core, matters, provenance | PASS | Deterministic local acceptance and evidence-gap contracts are green. |
| Pavlik contracts | PASS | Synthetic gates rerun; prior private-source gate retained without exposing the source. |
| API/commands | PASS | Missing auth now fails closed; local unauthenticated use requires explicit opt-in. |
| Gmail | PASS | Exact `gmail.readonly`; list/get only; no attachment bytes, mutations, or link opening. |
| Outlook | PASS | List/read path and read-only Graph adapter covered; reply workflow remains review-only. |
| Apple | PASS | macOS/iOS compile; Keychain update and backend lifecycle paths reviewed. |
| Telegram | DEFERRED | Sending remains disabled/dry-run by default and is outside first-Beta scope. |
| Supabase | STAGING GATE | ACL migration is tracked but unapplied; isolated validation is mandatory. |
| Production/deploy | OUT OF SCOPE | No operation was performed or authorized. |

## Finalization fixes

1. Closed the default development API-auth bypass; `ALLOW_UNAUTHENTICATED_DEVELOPMENT` defaults to
   `false` and is documented as loopback development only.
2. Buffered Apple helper output until complete lines, preventing chunk-boundary parsing failures.
3. Stopped the backend when Keychain configuration persistence fails.
4. Replaced asynchronous app-termination cleanup with a synchronous interrupt path and verified the
   child server exits.
5. Aligned package/module/API versions at `0.7.0`.
6. Added the reviewed Supabase client-role `TRUNCATE` revocation as an unapplied migration plus an
   explicit isolated-environment gate.
7. Reconciled stale branch, PR, Gmail-gate, and test-count statements in release documentation.

## Gmail acceptance status

The first Beta connector is local, single-user, and read-only. OAuth uses the installed-app loopback
flow and exact `https://www.googleapis.com/auth/gmail.readonly`. Credentials live in macOS Keychain.
The gateway exposes only message list/get, uses bounded snippets, records attachment/link metadata,
and saves a safe current-context snapshot. It cannot send, modify, label, archive, trash, delete,
download an attachment body, or open an external link.

The live owner-Mac gate passed earlier on 2026-08-27. This finalization intentionally used only
synthetic fixtures and did not inspect Gmail, OAuth material, or Keychain contents. A new owner setup
must follow `GMAIL_READONLY_PRIVATE_BETA.md`; no billing or card is required for the testing flow.

## Deferred work

- Validate Supabase ACL/RPC/worker behavior and rollback in an isolated project before production.
- Resolve GitHub Actions infrastructure independently of the green local release gates.
- Clean up the unreferenced legacy Gmail client and conflicting legacy `inbox/` package in a focused,
  non-release refactor.
- Installer/notarization/update-channel and broader multi-user privacy onboarding remain outside 0.7.

## Release decision

The only next release action is owner review of the Draft PR into
`release/jafar-private-beta-0.7`. Do not merge or mark it ready without explicit approval.
