# Jafar Private Beta release checklist

Target: **2026-09-15**

This checklist is for the first private Beta only. It does not authorize production database changes, autonomous legal actions, or external publication/sending without human approval.

## 1. Repository and branch control

- [ ] Working branch is `codex/beta-readiness-audit` and local tree is clean.
- [ ] PR #26 is mergeable and contains only intended Beta changes.
- [ ] `main` remains untouched until explicit release decision.
- [ ] No client PDF, mailbox content, tokens, API keys, or credentials exist in tracked files.
- [ ] Superseded experimental branches/PRs are not merged into the Beta line.

## 2. Python quality gate

Run locally from repository root:

```bash
python3 -m ruff check src tests scripts
python3 -m pytest -q
```

Expected current control point:

- Ruff: `All checks passed!`
- pytest: `197 passed, 1 warning` or higher after intentional new tests
- only known non-blocking warning: Starlette/TestClient deprecation

- [ ] Ruff passes.
- [ ] Full pytest suite passes.
- [ ] No new warning affects legal correctness, security, privacy, or runtime stability.

## 3. Apple build gate

From `apple/`:

```bash
xcodegen generate --spec project.yml
xcodebuild -project JafarApp.xcodeproj -target JafarApp_macOS -sdk macosx CODE_SIGNING_ALLOWED=NO build
```

For iOS Simulator use the existing simulator target/configuration.

- [ ] macOS build succeeds.
- [ ] iOS Simulator build succeeds.
- [ ] API endpoint is not hard-coded to a production secret-bearing URL.
- [ ] API key remains device-only in Keychain.

## 4. Live Apple command gate

Use the loopback private-Beta backend smoke helper and an ephemeral API key.

- [ ] Backend binds only to loopback for local smoke.
- [ ] `проверка связи` reaches `/v1/command`.
- [ ] Response renders in Jafar.
- [ ] Response is spoken aloud.
- [ ] Ephemeral API key is destroyed after the smoke.
- [ ] No temporary secret is committed or saved in project files.

Current verified baseline: **PASS**.

## 5. Pavlik private legal-document gate

Run only against the local private PDF. Never commit the document.

Current verified baseline:

`PAVLIK PRIVATE E2E: PASS`

Required safety assertions:

- [ ] investigator motion is not mislabeled as a court decision;
- [ ] investigation allegations remain `investigation_allegation`;
- [ ] historical admissions are not promoted to immutable current defense position;
- [ ] detected source anomalies remain evidence gaps;
- [ ] private PDF is not committed;
- [ ] external AI is not called by the local acceptance harness;
- [ ] production is not written.

## 6. Outlook / email gate

Private Beta live strategy: **installed Microsoft Outlook connector**.

- [ ] Connected Outlook mailbox can be listed/read.
- [ ] No send/delete/move/archive operation is performed during validation.
- [ ] Legal-context messages can enter triage/analysis workflows.
- [ ] Unsupported/oversized/materialization-failed attachments are surfaced explicitly.
- [ ] ZIP files are not silently dropped.
- [ ] Draft replies remain review-only.
- [ ] No mailbox content or attachment bytes are committed to GitHub.

Direct standalone Microsoft Graph OAuth is **deferred**. The Graph client and Device Code helper remain tested future infrastructure, not a first-Beta release blocker.

## 7. Human-approval safety gate

- [ ] `prepare_reply` reports `requires_review=true`.
- [ ] `send_performed=false` unless a separately confirmed send action is explicitly invoked in a future approved workflow.
- [ ] Legal filings, legal email sends, Telegram legal replies, and production changes remain human-controlled.
- [ ] External AI remains disabled by default.

## 8. Packaging / local runtime polish

- [ ] Normal packaged/installed runtime imports `jafar` without a manual `PYTHONPATH=src` workaround.
- [ ] macOS app launches from the built application bundle.
- [ ] README/release notes explain local Beta setup without exposing secrets.

## 9. Deferred production gates — do not block Private Beta

These remain mandatory before any cloud/production Beta:

- [ ] isolated Supabase ACL test environment available;
- [ ] client roles cannot `TRUNCATE` protected legal tables;
- [ ] privileged RPC grants/search paths reviewed;
- [ ] worker/auth/retry migrations validated with rollback outside production;
- [ ] GitHub Actions startup/infrastructure blocker resolved or a documented equivalent release control exists.

## 10. Release decision

Private Beta may be declared only when sections 1–8 are green and there is no unresolved blocker affecting legal correctness, confidentiality, or human-control guarantees.

Final release record should include:

- release date;
- commit SHA;
- Python/Ruff results;
- Apple build results;
- Pavlik gate result;
- Outlook connector validation result;
- known non-blocking warnings;
- confirmation that `main`/production changes were deliberate and separately approved.
