# Jafar Beta readiness — 2026-08-25

## Executive status

**Verified private-Beta readiness: 72%.**  
**Implemented readiness awaiting the next local gate: ~80%.**

The verified score reflects code that has already passed local regression checks on the user's Mac. The implemented score includes the latest Apple, Outlook and command-surface work that is isolated in the audit branch but still needs the next combined local gate.

**Target private Beta date: 2026-09-15.**

A cloud/production Beta should not be declared before database permissions and worker migrations are validated in an isolated Supabase environment. The working cloud/production target remains **2026-09-29**, conditional on that isolated database gate.

## Last verified control point

On `codex/beta-readiness-audit`, the last local macOS control point is:

- full Python suite: **186 passed, 1 warning**;
- Ruff: **passed** after applying its canonical import-order fix;
- real private 4-page Pavlik investigator-motion PDF E2E: **PASS**;
- no private PDF or secret committed;
- external AI disabled by default;
- production and `main` untouched.

The remaining warning is the existing FastAPI/Starlette TestClient deprecation warning.

## Readiness by subsystem

| Subsystem | Readiness | Current assessment |
| --- | ---: | --- |
| Document intake + Pavlik acceptance | 90% | Real source passed local E2E; page-preserving extraction, provenance and evidence gaps work. |
| Legal reasoning + safety | 84% | Source types, confidence handling, chronology and human-review gates are in place. |
| FastAPI / command core | 85% implemented | First four practical lawyer commands are now implemented; latest batch awaits local regression. |
| Email intelligence pipeline | 78% implemented | Outlook read-only orchestration and synthetic end-to-end acceptance flow are implemented; one live private Outlook validation remains. |
| Apple voice/client | 72% implemented | Remote API client, Keychain-backed key, runtime configuration and real App Intent execution are implemented; build and live smoke tests remain. |
| Telegram | 65% | Safe runtime exists; not required for the first private Beta exit. |
| Model routing | 65% | Multi-provider abstractions exist; external AI remains explicit opt-in. |
| Persistence / Supabase | 55% | Production ACL/RPC and worker migrations still require isolated database validation. |
| API/security boundary | 85% | Fail-closed API-key boundary and provider safety regression tests have passed locally. |
| CI / release operations | 45% | Workflows exist, but GitHub Actions currently fails at startup before jobs execute. |

## Fixed or implemented in `codex/beta-readiness-audit`

1. Fail-closed `X-Jafar-API-Key` protection for private `/v1/*` endpoints and legal-entity routes.
2. OpenAI document-path object/string mismatch fixed.
3. Provider configuration unified through Pydantic settings.
4. Deterministic local fallback when configured external analysis fails at runtime.
5. External AI is explicit opt-in (`EXTERNAL_AI_ENABLED=false` by default), preventing accidental spend or data egress.
6. Explicit `matter_id` is authoritative for document persistence.
7. Package/service version aligned to `0.6.0`.
8. Apple remote client uses the same API-key header contract as the backend.
9. Apple API endpoint is stored in UserDefaults and API key in device-only Keychain storage; no key is committed.
10. Apple voice screen switches to the configured remote client and can reconfigure at runtime.
11. App Intent executes the real backend command and reports missing configuration transparently.
12. App Shortcut phrases use the application-name token required by the App Intents contract.
13. Speech delegate lifetime is retained correctly.
14. Canonical PR trigger coverage is present in Python and Apple workflows.
15. Outlook provider prefers the full plain-text body and falls back to `bodyPreview` for HTML bodies instead of passing raw markup.
16. `OutlookReadOnlyService` now composes Outlook -> provider-neutral email -> triage -> attachment intake -> document workflow -> matter match -> review-only draft, with no send/archive/delete capability.
17. Outlook read-only synthetic E2E covers attachment materialization, matter linkage, idempotency, review-only draft and shared lawyer context.
18. First four Beta commands are implemented:
   - `Что требует моего внимания?`
   - `Что нового по делу …?`
   - `Разбери последнее юридическое письмо`
   - `Подготовь ответ`
19. `Подготовь ответ` only exposes a draft with `requires_review=true` and `send_performed=false`; it does not send email.
20. Superseded/divergent PRs were closed so the active development line is intentional and auditable.

## Still blocking the private Beta exit

1. Run the next combined Python/Ruff regression gate for the latest Outlook/command commits.
2. Pass iOS Simulator and macOS Apple build gates.
3. Perform one live local Apple -> `/v1/command` smoke test using Keychain-backed configuration.
4. Validate one real, private, read-only Outlook message through the same pipeline without committing its content.
5. Reconfirm Pavlik private PDF E2E after the branch is consolidated.

## Blocking cloud/production Beta, but not private Beta

1. Validate the Supabase ACL hardening candidate in an isolated database before any production change.
2. Confirm client roles cannot obtain dangerous privileges such as `TRUNCATE` on RLS-protected legal tables.
3. Review `record_document_event(...)` execution grants and privileged RPC search paths.
4. Validate worker/auth/retry migrations and rollback outside production.
5. Restore a reliable CI execution path; current GitHub Actions runs fail at startup before jobs begin.

## Beta scope

The first private Beta remains intentionally narrow:

- Mac/iPhone/iPad voice and text command shell;
- read-only legal document and email analysis;
- matter matching, chronology, deadlines, risks and evidence gaps;
- reply/document drafting for lawyer review;
- explicit human control before consequential external actions;
- external AI disabled by default;
- no autonomous filing, sending, deletion or publishing;
- production database changes excluded until isolated validation exists.

## Beta exit gate

Private Beta can be tagged only when all of the following are true:

- full Python suite passes;
- Ruff passes;
- iOS Simulator and macOS builds pass;
- Pavlik private PDF E2E remains green;
- Outlook read-only synthetic E2E is green;
- one private Outlook read-only validation is green;
- API auth tests are green;
- Apple remote-client command reaches `/v1/command` without secrets in Git;
- approval/review gates remain enforced;
- no client document or secret is committed.

## Current stop point

The legal-document core and backend audit are locally verified. The latest autonomous batch has implemented the **Outlook read-only vertical, shared legal-email context, the first four lawyer commands, and App Intent phrase hardening**. The next control point is one combined local Python/Ruff gate, followed by the Apple build gate. `main` and production remain untouched.
