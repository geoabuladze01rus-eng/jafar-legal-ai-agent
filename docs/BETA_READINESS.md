# Jafar Beta readiness — 2026-08-26

## Executive status

**Verified private-Beta readiness: ~99%.**

All substantive Private Beta quality, legal-safety, Apple, Outlook, packaging, and live-command gates are green. The only remaining pre-declaration action is operational cleanup of the final ephemeral loopback backend/API key plus the explicit release decision. Cloud/production hardening remains separate and is not part of this Private Beta gate.

**Target private Beta date: 2026-09-15.**

A cloud/production Beta should not be declared before database permissions and worker migrations are validated in an isolated Supabase environment. The working conditional cloud target remains **2026-09-29**.

## Latest verified control point

Locally on macOS:

- normal wheel installation without `PYTHONPATH`: **PASS**;
- installed-package `import jafar`: **PASS**;
- Python: **211 passed, 1 warning**;
- Ruff: **All checks passed**;
- private-Beta backend smoke: **PASS** (`PRIVATE BETA BACKEND SMOKE: PASS`);
- iOS Simulator build: **PASS**;
- macOS build: **PASS**;
- macOS Jafar launch: **PASS**;
- endpoint and API key persistence: **PASS**;
- live macOS Jafar command `проверка связи` -> authenticated `/v1/command`: **PASS** end-to-end;
- macOS Jafar rendered the response and spoke `Джафар на связи`;
- real private 4-page Pavlik investigator-motion PDF E2E on the current beta branch: **PASS**;
- connected Outlook mailbox read access through the installed Microsoft Outlook connector: **PASS**;
- local Gmail read-only gateway and synthetic HTTP command E2E: **PASS**;
- live Gmail OAuth and Keychain-backed command-runtime read: **PASS**;
- final live Gmail command through the macOS app UI: **pending**;
- unsupported real ZIP attachment visibility path confirmed;
- no private PDF, mailbox content, or secret committed;
- production and `main` untouched.

The remaining Python warning is the existing non-blocking Starlette/httpx TestClient deprecation warning.

## Readiness by subsystem

| Subsystem | Readiness | Audit assessment |
| --- | ---: | --- |
| Document intake + Pavlik acceptance | 98% | Real source passed current-branch local E2E; page-preserving extraction, provenance and evidence gaps are working. |
| Legal reasoning + safety | 94% | Source types, confidence handling, human-review gates and chronology are active. Broader real-document coverage remains useful but is not a first-Beta blocker. |
| FastAPI / command core | 98% | Core endpoints, API auth and first four lawyer commands exist; live Apple round trip passed. |
| Email intelligence pipeline | 98% | Triage, attachments, idempotency, matter matching, review-only drafts and synthetic Outlook E2E exist; Gmail passes offline E2E plus a live Keychain-backed list/read/context check, with the final macOS UI round trip pending. |
| Apple voice/client | 98% | Remote client, Keychain-backed API key, App Intent, iOS/macOS builds and live spoken-response smoke passed. |
| Telegram | 65% | Runtime, inbound/outbound, approval and safety layers exist; not required for first private Beta. |
| Model routing | 65% | OpenAI/Gemini/DeepSeek abstractions exist; external AI remains explicit opt-in. |
| Persistence / Supabase | 55% | Significant persistence/migrations exist; production ACL/RPC review still requires isolated database validation. |
| API/security boundary | 94% | Fail-closed API key for `/v1/*`; legal external actions remain review-gated. |
| CI / release operations | 75% | Local Mac gates are authoritative and green; GitHub Actions still has an account/infrastructure startup blocker. |

## Audit fixes implemented in `codex/beta-readiness-audit`

1. Fail-closed `X-Jafar-API-Key` boundary for `/v1/*` and legal-entity routes.
2. Resilient local/provider analysis path and explicit external-AI opt-in.
3. Configured-OpenAI document object/string runtime bug fixed.
4. Explicit `matter_id` persistence fixed.
5. Package/service version aligned at `0.6.0`.
6. Apple endpoint in UserDefaults and API key in device-only Keychain.
7. Apple main voice screen uses configured remote backend.
8. App Intent executes the real backend command.
9. Speech delegate lifetime fixed.
10. Swift/Pydantic command payload contract aligned via snake_case coding keys.
11. Outlook full plain-text body preferred; HTML body falls back to safe preview.
12. Read-only Outlook orchestration through email/document/matter pipeline.
13. Synthetic Outlook E2E covers attachment processing, matter linkage, idempotency and review-only draft.
14. First four lawyer commands implemented: attention summary, matter update, latest legal email, prepare reply.
15. `prepare_reply` never sends and reports `requires_review=true`, `send_performed=false`.
16. Canonical CI trigger coverage and repository hygiene improved.
17. Unsupported/oversized/materialization-failed Outlook attachments are surfaced as `AttachmentProcessingIssue` records instead of being silently skipped.
18. Local Microsoft Graph adapter plus Device Code auth helper are implemented and unit-tested as a future direct-Graph path; direct Azure/Entra registration is deliberately deferred and is not required for the first private Beta.
19. `pytest` src-layout import path is deterministic via project configuration.
20. A normal wheel installation imports `jafar` without `PYTHONPATH`; this is the recommended Private Beta installation path.
21. README and release checklist now document the verified Beta setup and the wheel-install recommendation.
22. Local Gmail uses an installed-app loopback flow with exact `gmail.readonly`, Keychain-backed
    credentials, list/get-only operations, bounded body parsing, and metadata-only attachment/link
    handling.
23. Synthetic Gmail HTTP E2E confirms newest-relevant selection, current-context persistence, and
    zero mailbox mutation without a real account or credential.

## Gmail strategy for first private Beta

Gmail is a local, single-user, read-only connector. The command path passes offline coverage and a
live owner-Mac check using a Google OAuth Desktop app client. Tokens and the desktop client bundle
are never committed; the authorized credential is held in local Keychain. The live check selected
a legal message and stored the safe current context without changing the mailbox, downloading an
attachment, or opening a link. The final command round trip through the macOS app UI remains.

No billing, Supabase, production service, deployment, or automatic reply is part of this path.
See [`GMAIL_READONLY_PRIVATE_BETA.md`](GMAIL_READONLY_PRIVATE_BETA.md).

## Outlook strategy for first private Beta

The first private Beta uses the already connected Microsoft Outlook connector as the live mailbox boundary. This path is confirmed to list/read real messages without sending, deleting, moving, or modifying mail.

The repository also contains a direct Microsoft Graph Outlook client and Device Code auth helper. That path remains future standalone infrastructure and is deliberately deferred until a dedicated Microsoft/Entra application registration is practical.

No Azure subscription or card is required for the current private-Beta Outlook path.

## Live Apple validation completed

- Local staging backend bound to `127.0.0.1` only.
- Ephemeral API key used; no key written to Git or project files by the smoke helper.
- Backend acceptance helper returned `PRIVATE BETA BACKEND SMOKE: PASS`.
- Jafar macOS app launched and connected through the configured endpoint and Keychain-backed API key.
- Endpoint and API key persistence were confirmed.
- Command `проверка связи` reached `/v1/command` end-to-end, returned a successful response, rendered in the app, and produced the confirmed spoken response `Джафар на связи`.
- No production service or database was touched.

## Packaging validation completed

- The package was built and installed as a normal wheel.
- The installed package works without setting `PYTHONPATH`.
- `import jafar` after installation: **PASS**.
- For Private Beta, use the normal wheel installation path. On macOS with Python 3.12, an editable install may rely on a hidden `.pth` file, which can make local import diagnosis misleading; this behavior is non-blocking and is not the recommended Beta installation method.

## Real Outlook validation completed

- Connected Outlook mailbox read access confirmed through the installed Microsoft Outlook connector.
- Real mailbox messages can be listed/read in read-only mode.
- A real non-inline ZIP attachment confirmed the explicit unsupported-attachment safety path.
- No message was sent, deleted, moved, or modified during validation.
- No private mailbox content, attachment bytes, message IDs, client documents, or secrets were committed to GitHub.

## Real Pavlik validation completed

- Current beta branch rerun on the private 4-page investigator motion returned `PAVLIK PRIVATE E2E: PASS`.
- Privacy flags remained fail-safe: private PDF not committed, external AI not called, production not written.
- Source attribution/evidence-gap behavior remains active.

## Final PR review status

PR #26 is open, mergeable, has no review submissions, no inline review threads, and no PR discussion comments at the final review point. The PR remains intentionally Draft until the final ephemeral loopback backend is stopped and the release decision is explicit.

GitHub reports no commit status checks for the current head; this is consistent with the known Actions startup/infrastructure problem. Local Mac validation remains the authoritative zero-budget release control.

## Still blocking formal Private Beta declaration

1. Stop the final loopback backend process so the ephemeral API key is no longer active.
2. Explicitly mark PR #26 ready for review / approve the Private Beta release decision.

## Technical debt / non-blockers

- Starlette/httpx TestClient deprecation warning;
- editable installs on macOS/Python 3.12 may rely on a hidden `.pth`; use a normal wheel installation for the Private Beta;
- direct standalone Microsoft Graph OAuth is deferred until a dedicated Entra registration is practical;
- GitHub Actions startup failure remains an account/infrastructure blocker, so local Mac gates are authoritative for the zero-budget Beta.

## Blocking cloud/production Beta, but not private Beta

1. Validate Supabase ACL hardening in an isolated database before production changes.
2. Verify client roles cannot obtain dangerous table privileges such as `TRUNCATE` on RLS-protected legal tables.
3. Review `record_document_event(...)` execution grants and privileged RPC search paths.
4. Validate worker/auth/retry migrations and rollback procedure outside production.
5. Restore a reliable GitHub Actions execution path.

## Beta scope

The first private Beta remains deliberately narrow:

- Mac/iPhone/iPad voice/text command shell;
- read-only legal document and email analysis;
- matter matching, chronology, deadlines, risks and evidence gaps;
- reply/document drafting for review;
- explicit human approval before consequential external action;
- external AI disabled by default and enabled only deliberately;
- Outlook live access through the installed connector;
- no autonomous filing, sending or publishing;
- production database changes excluded until isolated validation exists.

## Beta exit gate

Private Beta can be tagged only when all of the following are true:

- full Python suite passes;
- Ruff passes;
- iOS Simulator and macOS builds pass;
- Pavlik private PDF E2E remains green;
- Outlook read-only live access remains available through the connector;
- real Outlook skipped/unsupported attachments are visible to the lawyer rather than silently dropped;
- API auth tests are green;
- Apple remote-client command reaches `/v1/command` without secrets in Git;
- approval gates remain enforced;
- no client document, mailbox content or secret is committed;
- release checklist is signed off locally;
- the final ephemeral loopback backend is stopped.

## Current stop point

Core backend, normal wheel packaging/import, the 211-test Python suite, Ruff, first four commands, Apple launch and live voice round trip, current-branch Pavlik E2E, Outlook connector read access, synthetic Outlook/Gmail E2E, Graph adapter tests, Apple compilation gates, repository cleanup, and release documentation are green. Live Gmail remains intentionally stopped at its owner-credential setup gate. The next release action is still separate from this branch. No merge to `main` and no production change is part of that action.
