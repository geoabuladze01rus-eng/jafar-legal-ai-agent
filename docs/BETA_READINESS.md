# Jafar Beta readiness — 2026-08-25

## Executive status

**Overall private-Beta readiness: 68%.**

This score reflects working code and verified contracts, not file count. The document/legal core is substantially ahead of the connected-client and production-operational layers.

**Target private Beta date: 2026-09-15.**

A cloud/production Beta should not be declared before database permissions and worker migrations are validated in an isolated Supabase environment. With a zero-budget local Supabase/Docker validation path, the working target is **2026-09-29**; without an isolated database gate, that date remains conditional.

## Last verified control point

Before this audit branch was created, `codex/canonical-pavlik-gate` was verified locally on macOS with:

- `178 passed, 1 warning` for the full Python test suite;
- Ruff: `All checks passed!`;
- real private 4-page Pavlik investigator-motion PDF E2E: `PASS`;
- `human_review_required=true` for legally attributed findings;
- the investigator request remained distinct from a court decision;
- expected source anomalies were surfaced as evidence gaps;
- no private PDF was committed;
- no external AI was called by the private E2E;
- production was not written.

The remaining test warning is the existing FastAPI/Starlette TestClient deprecation warning.

## Readiness by subsystem

| Subsystem | Readiness | Audit assessment |
| --- | ---: | --- |
| Document intake + Pavlik acceptance | 90% | Real source passed local E2E; page-preserving extraction, provenance and evidence gaps are working. |
| Legal reasoning + safety | 82% | Source types, confidence handling, human-review gates and chronology exist. Broader real-document coverage is still needed. |
| FastAPI / command core | 75% | Core endpoints and command runtime work; natural-language command routing is still narrow. |
| Email intelligence pipeline | 62% | Triage, attachments, idempotency, matter matching and review-only drafts exist. Real Gmail/Outlook connector execution is not yet end-to-end. |
| Apple voice/client | 45% | Speech recognition/synthesis and App Intent shell exist, but `ContentView` still uses `LocalCommandClient`; Siri intent does not yet execute the backend command. |
| Telegram | 65% | Runtime, inbound/outbound, approval and safety layers exist; not required for the first private Beta exit. |
| Model routing | 65% | OpenAI/Gemini/DeepSeek abstractions and privacy routing exist, but the main legal API still prioritizes the structured OpenAI analyzer rather than the full multimodel router. |
| Persistence / Supabase | 55% | Significant migrations, worker separation, retry and recovery code exist. Production ACL/RPC review still requires isolated database validation. |
| API/security boundary | 70% after audit patch | Audit branch adds fail-closed API-key protection for `/v1/*`; must pass the local regression gate before merge. |
| CI / release operations | 45% | Workflows exist, but GitHub Actions has an account/infrastructure startup blocker. Canonical PR trigger coverage is patched in this audit branch. |

## Critical findings from the audit

### Fixed in `codex/beta-readiness-audit`

1. **Unauthenticated private API surface.** `/v1/*` endpoints and legal-entity routes had no authentication dependency. A fail-closed `X-Jafar-API-Key` boundary is now added for non-development environments.
2. **OpenAI document path type error.** The document endpoint could pass an `ExtractedDocument` object to an analyzer that requires `str`, causing a runtime failure when OpenAI was configured. The endpoint now routes through one resilient analyzer and always analyzes extracted text.
3. **Provider configuration mismatch.** Main application initialization checked `os.getenv()` rather than the already-loaded settings object. The audit branch uses the Pydantic settings object consistently.
4. **Provider outage behavior.** The main legal path could fail hard on a provider runtime error. The audit branch falls back to deterministic local legal heuristics while preserving invalid-input errors.
5. **Accidental external-AI spend/data egress risk.** Merely having an API key available could activate the external provider path. External AI is now explicit opt-in with `EXTERNAL_AI_ENABLED=false` by default.
6. **Explicit matter-link persistence bug.** `/v1/documents/analyze?matter_id=...` could return the requested matter ID without guaranteeing that the document event/deadlines were persisted to that matter. Explicit matter IDs are now authoritative in `DocumentWorkflow` and covered by a regression test.
7. **Version drift.** Package metadata was `0.3.1` while the FastAPI service reported `0.6.0`. Package metadata is aligned to `0.6.0`.
8. **Apple authentication mismatch.** The Swift remote client sent `Authorization: Bearer`, while the hardened API contract uses `X-Jafar-API-Key`. The client now uses the same header contract.
9. **Apple speech delegate lifetime.** The speech synthesizer delegate was not retained strongly, which could leave `isSpeaking` stuck. The view model now retains the delegate for the duration of speech.
10. **Canonical CI coverage.** Python and Apple workflows only targeted `main`. They now also target pull requests into `codex/jafar-canonical-v2`.
11. **Repository hygiene.** Superseded/divergent PRs were closed so the active development line is limited to Pavlik/canonical, isolated DB hardening, and Beta audit stacks.

### Still blocking the private Beta exit

1. Wire the Apple app to a real `RemoteCommandClient` with a secure user-configured endpoint/key; do not commit secrets.
2. Make the App Intent actually execute a Jafar command instead of only returning a placeholder dialog.
3. Complete one real read-only Outlook flow: Outlook message -> provider-neutral message -> email pipeline -> matter match -> attachments -> brief/draft -> human review.
4. Add an end-to-end acceptance test for that Outlook flow using a synthetic connector fixture and one local private-message validation.
5. Expand command routing beyond health/list-matters to the first four Beta commands: attention summary, matter update, latest legal email analysis, prepare reply.
6. Re-run the complete Python/Ruff and Apple build gates after the audit patches.

### Blocking cloud/production Beta, but not the local/private Beta

1. Validate the Supabase ACL hardening candidate in an isolated database before any production change.
2. Verify client roles cannot obtain dangerous table privileges such as `TRUNCATE` on RLS-protected legal tables.
3. Review `record_document_event(...)` execution grants and privileged RPC search paths.
4. Validate worker/auth/retry migrations and rollback procedure outside production.
5. Restore a reliable CI execution path; GitHub Actions currently has a startup/account-level blocker independent of the code test suite.

## Beta scope

The first private Beta is intentionally narrow:

- Mac/iPhone/iPad voice/text command shell;
- read-only legal document and email analysis;
- matter matching, chronology, deadlines, risks and evidence gaps;
- reply/document drafting for review;
- explicit human approval before any consequential external action;
- external AI disabled by default and enabled only deliberately;
- no autonomous filing, sending or publishing;
- production database changes excluded from the Beta gate until isolated validation exists.

## Beta exit gate

Private Beta can be tagged only when all of the following are true:

- full Python suite passes;
- Ruff passes;
- iOS Simulator and macOS builds pass;
- Pavlik private PDF E2E remains green;
- Outlook read-only E2E is green;
- API auth tests are green;
- Apple remote-client command reaches `/v1/command` without secrets in Git;
- approval gates remain enforced;
- no client document or secret is committed.

## Current stop point

The project stopped after hardening and successfully validating the real Pavlik investigator-motion E2E on `codex/canonical-pavlik-gate`. The next functional vertical is **Outlook -> existing email/document engine -> matter/case intelligence -> review-only draft**, while the audit branch removes Beta-level security and client defects in parallel.
