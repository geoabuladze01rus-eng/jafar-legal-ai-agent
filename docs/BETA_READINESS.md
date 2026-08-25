# Jafar Beta readiness — 2026-08-25

## Executive status

**Verified private-Beta readiness: ~85%.**

This score reflects working code plus locally verified control gates. The remaining risk is concentrated in live connector/runtime smoke tests and production-database hardening, not in the core legal document pipeline.

**Target private Beta date: 2026-09-15.**

A cloud/production Beta should not be declared before database permissions and worker migrations are validated in an isolated Supabase environment. With a zero-budget local validation path, the working target remains **2026-09-29**; without an isolated database gate, that date remains conditional.

## Latest verified control point

Locally on macOS:

- Python: **194 passed, 1 warning**;
- Ruff: **All checks passed**;
- iOS Simulator build: **PASS**;
- macOS build: **PASS**;
- real private 4-page Pavlik investigator-motion PDF E2E baseline: **PASS**;
- no private PDF or secret committed;
- production untouched.

The remaining Python warning is the existing FastAPI/Starlette TestClient deprecation warning.

## Readiness by subsystem

| Subsystem | Readiness | Audit assessment |
| --- | ---: | --- |
| Document intake + Pavlik acceptance | 90% | Real source passed local E2E; page-preserving extraction, provenance and evidence gaps are working. |
| Legal reasoning + safety | 84% | Source types, confidence handling, human-review gates and chronology exist. Broader real-document coverage remains useful. |
| FastAPI / command core | 84% | Core endpoints, API auth and first four lawyer commands exist. Live Apple smoke remains. |
| Email intelligence pipeline | 80% | Triage, attachments, idempotency, matter matching, review-only drafts and synthetic Outlook E2E exist. Live Outlook boundary still needs one end-to-end runtime validation. |
| Apple voice/client | 82% | Remote client, Keychain-backed API key, App Intent and both iOS/macOS builds pass. Live `/v1/command` smoke remains. |
| Telegram | 65% | Runtime, inbound/outbound, approval and safety layers exist; not required for first private Beta. |
| Model routing | 65% | OpenAI/Gemini/DeepSeek abstractions exist; external AI remains explicit opt-in. |
| Persistence / Supabase | 55% | Significant persistence/migrations exist; production ACL/RPC review still requires isolated database validation. |
| API/security boundary | 85% | Fail-closed API key for `/v1/*`; legal external actions remain review-gated. |
| CI / release operations | 55% | Local Mac gates are reliable; GitHub Actions still has an account/infrastructure startup blocker. |

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
10. Outlook full plain-text body preferred; HTML body falls back to safe preview.
11. Read-only Outlook orchestration through email/document/matter pipeline.
12. Synthetic Outlook E2E covers attachment processing, matter linkage, idempotency and review-only draft.
13. First four lawyer commands implemented: attention summary, matter update, latest legal email, prepare reply.
14. `prepare_reply` never sends and reports `requires_review=true`, `send_performed=false`.
15. Canonical CI trigger coverage and repository hygiene improved.
16. Live Outlook mailbox review exposed a real operational defect: unsupported/oversized/materialization-failed attachments could be silently skipped. The provider now surfaces those as `AttachmentProcessingIssue` records instead of hiding them or aborting the mailbox. This is particularly important for legal archive attachments such as `.zip` files, which remain intentionally unsupported until a bounded archive-extraction design is added.

## Live Outlook review performed

A real connected Outlook mailbox was read in read-only mode. Message bodies/metadata and attachment metadata were accessible. A legal-context message with a non-inline ZIP attachment was found. The current Beta document intake intentionally does not extract ZIP archives, but the audit identified that the adapter previously skipped such files silently. The branch now records an explicit unsupported-attachment issue so the lawyer is told that material exists but was not analyzed.

No message was sent, deleted, moved or modified during this review, and no private mailbox content was committed to GitHub.

## Still blocking private Beta exit

1. Re-run Python/Ruff after the latest Outlook attachment-visibility patch.
2. One local Apple -> `/v1/command` smoke test with the Keychain-backed API key.
3. One live Outlook -> Jafar runtime validation using a supported attachment type (PDF/DOCX/TXT/MD), if available; otherwise validate the explicit unsupported-attachment warning path against the real ZIP message.
4. Final Pavlik E2E reconfirmation after consolidation.

## Blocking cloud/production Beta, but not private Beta

1. Validate Supabase ACL hardening in an isolated database before production changes.
2. Verify client roles cannot obtain dangerous table privileges such as `TRUNCATE` on RLS-protected legal tables.
3. Review `record_document_event(...)` execution grants and privileged RPC search paths.
4. Validate worker/auth/retry migrations and rollback procedure outside production.
5. Restore a reliable GitHub Actions execution path; current runs fail before jobs begin.

## Beta scope

The first private Beta remains deliberately narrow:

- Mac/iPhone/iPad voice/text command shell;
- read-only legal document and email analysis;
- matter matching, chronology, deadlines, risks and evidence gaps;
- reply/document drafting for review;
- explicit human approval before consequential external action;
- external AI disabled by default and enabled only deliberately;
- no autonomous filing, sending or publishing;
- production database changes excluded until isolated validation exists.

## Beta exit gate

Private Beta can be tagged only when all of the following are true:

- full Python suite passes;
- Ruff passes;
- iOS Simulator and macOS builds pass;
- Pavlik private PDF E2E remains green;
- Outlook read-only E2E is green;
- real Outlook skipped/unsupported attachments are visible to the lawyer rather than silently dropped;
- API auth tests are green;
- Apple remote-client command reaches `/v1/command` without secrets in Git;
- approval gates remain enforced;
- no client document, mailbox content or secret is committed.

## Current stop point

Core backend, first four commands, synthetic Outlook E2E and Apple compilation gates are green. The current audit patch hardens real-mail behavior so skipped Outlook attachments are surfaced for review. The next control gate is one combined local Python/Ruff run, followed by live Apple `/v1/command` and live Outlook smoke validation.