# Jafar — AI Legal Agent

Private AI assistant for legal practice: document and case analysis, email triage,
drafting, deadlines, voice workflows and controlled automation.

## Current status

Jafar is in pre-Beta development. The current canonical line already contains:

- FastAPI legal-work API and matter/command runtime;
- structured OpenAI legal analysis with deterministic local fallback;
- page-preserving PDF/DOCX/text intake and document-to-matter matching;
- chronology, evidence/provenance, contradiction and risk layers;
- email triage, attachment processing, idempotency and review-only reply drafting;
- Outlook provider-neutral adapter and Gmail ingestion contracts;
- Apple SwiftUI voice shell, speech recognition/synthesis and App Intents;
- Telegram runtime with approval/safety boundaries;
- Supabase persistence, document-worker, retry/recovery and audit infrastructure;
- explicit human-approval gates for consequential external actions.

The real private Pavlik investigator-motion acceptance flow has passed locally without
committing the source PDF or writing to production. See
[`docs/BETA_READINESS.md`](docs/BETA_READINESS.md) for the current readiness score,
blockers and target dates.

## Local start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn jafar.main:app --reload
```

Health check: `GET http://127.0.0.1:8000/health`

In non-development environments, private `/v1/*` endpoints require the
`X-Jafar-API-Key` header when the Beta-readiness hardening branch is merged. Secrets
must be supplied through environment/secret storage, never committed.

## Immediate Beta roadmap

1. Complete the Apple remote-client path and real App Intent execution.
2. Run a real read-only Outlook message through the existing email/document engine.
3. Expand the command router to the first four practical lawyer workflows.
4. Keep the Pavlik real-document acceptance gate green while broadening document coverage.
5. Validate Supabase ACL/RPC hardening outside production before any cloud Beta cutover.
6. Restore reliable CI execution and complete the private-Beta exit gate.

## Security rule

No credentials, tokens, private documents or client secrets belong in Git.
Consequential external actions require explicit approval.

## Project documentation

- [Beta readiness](docs/BETA_READINESS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Production document pipeline](docs/DOCUMENT_PIPELINE.md)
- [Production-readiness and synthetic E2E runbook](docs/PRODUCTION_RUNBOOK.md)
- [Security baseline](docs/CONSOLIDATION_SECURITY.md)
