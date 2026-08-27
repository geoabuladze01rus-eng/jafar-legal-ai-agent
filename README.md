# Jafar — AI Legal Agent

Private AI assistant for legal practice: document and case analysis, email triage,
drafting, deadlines, voice workflows and controlled automation.

## Current status

Jafar is at the **Private Beta release-candidate** stage.

Latest verified local control point on macOS:

- normal wheel installation without `PYTHONPATH`: **PASS**;
- `import jafar`: **PASS**;
- Ruff: **All checks passed!**;
- pytest: **211 passed, 1 warning**;
- iOS Simulator build: **PASS**;
- macOS build: **PASS**;
- private-Beta loopback backend smoke: **PASS**;
- live macOS Jafar -> authenticated `/v1/command`: **PASS**, including spoken response;
- real private Pavlik investigator-motion E2E: **PASS**;
- Outlook mailbox list/read through the installed Microsoft Outlook connector: **PASS**;
- local Gmail read-only command path with synthetic HTTP E2E: **PASS**;
- live Gmail OAuth and Keychain-backed command-runtime read: **PASS**;
- final live Gmail command through the macOS app UI: **PASS**.

Target Private Beta date: **2026-09-15**.

The remaining warning is the known non-blocking Starlette/httpx TestClient deprecation.
Cloud/production Beta remains conditional on isolated Supabase ACL/RPC/worker validation.

See [`docs/BETA_READINESS.md`](docs/BETA_READINESS.md) and
[`docs/PRIVATE_BETA_RELEASE_CHECKLIST.md`](docs/PRIVATE_BETA_RELEASE_CHECKLIST.md).

## Private Beta local setup

Use a normal package installation for the Private Beta runtime. On this macOS/Python 3.12
setup, editable installs may rely on a hidden `.pth` file, so `pip install -e .` is not the
recommended Beta acceptance path.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install '.[dev]'
```

Verify the installed package:

```bash
python3 -c 'import jafar; print(jafar.__file__)'
python3 -m ruff check src tests scripts
python3 -m pytest -q
```

Start the local API only with secrets supplied through environment/secret storage:

```bash
uvicorn jafar.main:app --host 127.0.0.1 --port 8000
```

Health check: `GET http://127.0.0.1:8000/health`

Private `/v1/*` and legal-entity routes use the fail-closed `X-Jafar-API-Key` boundary on
the Beta-hardening line. Never commit API keys, tokens, mailbox content, or client files.

For the controlled loopback acceptance path use the documented helper/runbook in
[`docs/APPLE_PRIVATE_BETA_SMOKE.md`](docs/APPLE_PRIVATE_BETA_SMOKE.md).

## First Private Beta scope

- Mac/iPhone/iPad voice and text command shell;
- read-only legal document and email analysis;
- matter matching, chronology, deadlines, risks and evidence gaps;
- review-only reply/document drafting;
- explicit human approval before consequential external action;
- Outlook live mailbox access through the installed Microsoft Outlook connector;
- external AI disabled by default unless deliberately enabled;
- no autonomous legal filing, email sending, Telegram legal reply, publication, or production change.

The repository also contains a direct Microsoft Graph Outlook client and Device Code auth
helper for a future standalone deployment. Direct Azure/Entra registration is deliberately
deferred and is not required for the first Private Beta.

## Local Gmail read-only gateway

The local backend now supports `Разбери последнее юридическое письмо` through a dedicated Gmail
gateway. It requests only `gmail.readonly`, keeps the OAuth credential bundle in the user's local
protected keychain, lists/reads Inbox messages, creates a short local summary, and records a safe
snapshot as the current lawyer context. It never sends, changes, archives, trashes, or deletes
mail. Attachments and external links are described but are not downloaded or opened.

Live authorization uses an owner-created Google OAuth client of type **Desktop app**. On the
verified owner Mac, the resulting grant is held in Keychain and the live command-runtime path
successfully selected a legal message and stored its safe snapshot without mailbox mutation,
attachment download, or external-link opening. The same command also passed through the macOS
app UI against its auto-started loopback backend. A Mac without that local grant still receives a
safe `setup_required` response; the app never asks for credentials. The complete zero-billing
setup and acceptance gate is documented in
[`docs/GMAIL_READONLY_PRIVATE_BETA.md`](docs/GMAIL_READONLY_PRIVATE_BETA.md).

## Security rule

No credentials, tokens, private documents, mailbox content or client secrets belong in Git.
Consequential external actions require explicit human approval.

## Project documentation

- [Private Beta release checklist](docs/PRIVATE_BETA_RELEASE_CHECKLIST.md)
- [Local Gmail read-only Private Beta](docs/GMAIL_READONLY_PRIVATE_BETA.md)
- [Beta readiness](docs/BETA_READINESS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Production document pipeline](docs/DOCUMENT_PIPELINE.md)
- [Production-readiness and synthetic E2E runbook](docs/PRODUCTION_RUNBOOK.md)
- [Security baseline](docs/CONSOLIDATION_SECURITY.md)
