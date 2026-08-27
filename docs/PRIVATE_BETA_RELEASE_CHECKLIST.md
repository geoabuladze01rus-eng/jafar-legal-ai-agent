# Jafar Private Beta 0.7 release checklist

Control point: **2026-08-27**

Target branch: `release/jafar-private-beta-0.7`

This checklist authorizes review only. It does not authorize production changes, merge, deployment,
mailbox mutation, sending, filing, publication, or use of private material in logs or Git.

## Repository and scope

- [x] Finalization branch starts from `codex/local-backend-autostart` at `15d8d7b`.
- [x] Divergent release-record commit is merged explicitly into finalization history.
- [x] Canonical Pavlik/legal core, Apple autostart, and merged Gmail gateway are present.
- [x] `main`, deployment, live mailbox state, and production Supabase were untouched.
- [x] No credentials, tokens, API keys, mailbox bodies, or private client files are tracked.

## Python and packaging

- [x] Ruff: **PASS**.
- [x] Full pytest: **218 passed, 1 known warning**.
- [x] Critical acceptance subset: **45 passed, 1 warning**.
- [x] Normal wheel installation without `PYTHONPATH`: **PASS**.
- [x] Package, module, and FastAPI versions agree at `0.7.0`.

The warning is the existing Starlette/httpx TestClient deprecation.

## Security and action boundaries

- [x] `/v1/*` fails closed when no API key is configured.
- [x] Unauthenticated development requires explicit local-only opt-in and defaults to disabled.
- [x] External AI defaults to disabled.
- [x] Reply preparation reports review required and does not send.
- [x] Telegram production sending remains disabled/dry-run by default.
- [x] No autonomous legal filing, submission, publication, or consequential outbound action exists.
- [x] Supabase ACL hardening is staged as an unapplied migration with an isolated validation gate.

## Gmail and Outlook

- [x] Gmail OAuth requests exactly `gmail.readonly` and stores credentials in macOS Keychain.
- [x] Gmail adapter exposes only `messages.list` and `messages.get`.
- [x] No Gmail send/draft-create/modify/label/archive/trash/delete/attachment-get path exists.
- [x] Links and attachment metadata are detected but never opened or downloaded by Gmail gateway.
- [x] Synthetic Gmail HTTP command E2E passes without credentials or a real account.
- [x] Prior owner-Mac live OAuth/runtime/UI gate passed; it was not rerun during finalization.
- [x] Outlook list/read and read-only Graph adapter tests pass.
- [x] Outlook reply remains review-only; oversized/unsupported attachment issues remain visible.

## Apple

- [x] macOS Debug build with signing disabled: **PASS**.
- [x] iOS Simulator Debug target build with signing disabled: **PASS**.
- [x] Microphone, speech recognition, local-network, and local-network transport keys are present.
- [x] Existing Keychain API-key item is updated before insert, avoiding duplicate-item regression.
- [x] Backend output uses complete-line buffering.
- [x] Keychain save failure stops the backend.
- [x] App termination interrupt and child-server cleanup: **PASS**.

## Legal acceptance

- [x] Pavlik acceptance, extension-motion, and private harness contracts pass in the focused suite.
- [x] Synthetic legal-document E2E passes.
- [x] Investigator material is not promoted to a court decision or immutable defense position.
- [x] Provenance and evidence-gap behavior remains active.
- [x] No private source was opened or logged during finalization.

## Before any production or wider release

- [ ] Validate Supabase ACL/RPC/worker changes and rollback in an isolated environment.
- [ ] Confirm installer, signing/notarization, update channel, observability, and privacy onboarding.
- [ ] Obtain separate approval for any deployment or production database change.
- [ ] Obtain explicit owner approval before merging or moving the Draft PR to ready-for-review.

## Release decision

Local Private Beta 0.7 gates are **PASS**. The next action is owner review of the Draft PR into the
release branch. No merge or status promotion is implied by this checklist.
