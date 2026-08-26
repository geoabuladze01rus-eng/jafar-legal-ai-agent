# Jafar Private Beta release checklist

Target: **2026-09-15**

This checklist is for the first private Beta only. It does not authorize production database changes, autonomous legal actions, or external publication/sending without human approval.

## 1. Repository and branch control

- [x] Working branch is `codex/beta-readiness-audit`; local cleanup of temporary Apple artifacts was completed.
- [x] PR #26 is mergeable and contains the intended Beta hardening stack.
- [x] `main` remains untouched until explicit release decision.
- [x] No client PDF, mailbox content, tokens, API keys, or credentials exist in tracked Beta files.
- [x] Superseded experimental branches/PRs are not merged into the Beta line.

## 2. Python quality gate

Run locally from the repository root with the project virtual environment:

```bash
.venv/bin/python -m ruff check src tests scripts
.venv/bin/python -m pytest -q
```

Expected current control point:

- Ruff: `All checks passed!`
- pytest: `199 passed, 1 warning`
- only known non-blocking warning: Starlette/httpx deprecation in TestClient coverage

- [x] Ruff passes: `All checks passed!`.
- [x] Full pytest suite passes: `199 passed, 1 warning`.
- [x] No new warning affects legal correctness, security, privacy, or runtime stability.

## 3. Apple build gate

From `apple/`:

```bash
xcodegen generate --spec project.yml
xcodebuild -project JafarApp.xcodeproj -target JafarApp_macOS -sdk macosx CODE_SIGNING_ALLOWED=NO build
```

For iOS Simulator use the existing simulator target/configuration.

- [x] macOS build succeeds.
- [x] iOS Simulator build succeeds.
- [x] API endpoint is configurable and is not a secret-bearing production URL hard-coded into the app.
- [x] API key remains device-only in Keychain.

## 4. Live Apple command gate

Use the loopback private-Beta backend smoke helper and an ephemeral API key.

- [x] Backend binds only to loopback for local smoke.
- [x] `PRIVATE BETA BACKEND SMOKE: PASS`.
- [x] Jafar macOS launches successfully.
- [x] Configured endpoint and API key persist successfully.
- [x] `проверка связи` reaches `/v1/command` end-to-end.
- [x] Response renders in Jafar.
- [x] Voice response `Джафар на связи` is confirmed.
- [ ] Ephemeral API key/backend process is stopped after the final smoke.
- [x] No temporary secret is committed or saved in tracked project files.

Current verified baseline: **PASS**, including the live macOS end-to-end voice round trip.

## 5. Pavlik private legal-document gate

Run only against the local private PDF. Never commit the document.

Current verified baseline:

`PAVLIK PRIVATE E2E: PASS`

Required safety assertions:

- [x] investigator motion is not mislabeled as a court decision;
- [x] investigation allegations remain `investigation_allegation`;
- [x] historical admissions are not promoted to immutable current defense position;
- [x] detected source anomalies remain evidence gaps;
- [x] private PDF is not committed;
- [x] external AI is not called by the local acceptance harness;
- [x] production is not written.

## 6. Outlook / email gate

Private Beta live strategy: **installed Microsoft Outlook connector**.

- [x] Connected Outlook mailbox can be listed/read.
- [x] No send/delete/move/archive operation is performed during validation.
- [x] Legal-context messages can be surfaced for triage/analysis through the connected Outlook workflow.
- [x] Unsupported/oversized/materialization-failed attachments are surfaced explicitly by the Jafar email pipeline.
- [x] ZIP files are not silently dropped by the legal-document path; they surface as unsupported material requiring review.
- [x] Draft replies remain review-only.
- [x] No mailbox content or attachment bytes are committed to GitHub.

Direct standalone Microsoft Graph OAuth is **deferred**. The Graph client and Device Code helper remain tested future infrastructure, not a first-Beta release blocker.

## 7. Human-approval safety gate

- [x] `prepare_reply` reports `requires_review=true`.
- [x] `send_performed=false` in the review-only workflow.
- [x] Legal filings, legal email sends, Telegram legal replies, and production changes remain human-controlled.
- [x] External AI remains disabled by default.

## 8. Packaging / local runtime polish

- [x] Normal wheel installation works without a manual `PYTHONPATH` workaround.
- [x] `import jafar` after the wheel installation: **PASS**.
- [x] Jafar macOS app launches successfully.
- [x] README explains the Private Beta local setup, wheel-install recommendation, safety boundary, and connector strategy without exposing secrets.

Known non-blocking packaging note: an editable install on macOS with Python 3.12 may use a hidden `.pth` file and can therefore be misleading during local import diagnosis. Use a normal wheel installation for the Private Beta runtime and acceptance gate.

## 9. Final verified Private Beta gate — 2026-08-26

- normal wheel installation without `PYTHONPATH`: **PASS**;
- `import jafar`: **PASS**;
- Ruff: `All checks passed!`;
- pytest: `199 passed, 1 warning`;
- backend: `PRIVATE BETA BACKEND SMOKE: PASS`;
- Jafar macOS launch: **PASS**;
- endpoint/API key persistence: **PASS**;
- command `проверка связи` end-to-end: **PASS**;
- spoken response `Джафар на связи`: **CONFIRMED**;
- real Pavlik private E2E: **PASS**;
- Outlook connector read-only access: **PASS**;
- PR #26: **OPEN / MERGEABLE / DRAFT** with no review submissions, no inline review threads and no PR discussion comments at final review;
- current GitHub head has no commit status checks because of the known Actions startup/infrastructure issue;
- `main` and production: **UNTOUCHED**.

Remaining observations are non-blocking: the Starlette/httpx deprecation warning and the macOS/Python 3.12 editable-install `.pth` behavior described above.

## 10. Deferred production gates — do not block Private Beta

These remain mandatory before any cloud/production Beta:

- [ ] isolated Supabase ACL test environment available;
- [ ] client roles cannot `TRUNCATE` protected legal tables;
- [ ] privileged RPC grants/search paths reviewed;
- [ ] worker/auth/retry migrations validated with rollback outside production;
- [ ] GitHub Actions startup/infrastructure blocker resolved or a documented equivalent release control exists.

## 11. Release decision

All substantive Private Beta gates are green. Before formally declaring/tagging the Private Beta or moving PR #26 out of Draft, complete the one operational cleanup item still unchecked in section 4: stop the final ephemeral loopback backend so its temporary API key is no longer active.

After that cleanup, PR #26 can be marked **Ready for review** without merging it into `main`.

Final release record should include:

- release date;
- commit SHA;
- Python/Ruff results;
- Apple build results;
- Pavlik gate result;
- Outlook connector validation result;
- known non-blocking warnings;
- confirmation that `main`/production changes were deliberate and separately approved.
